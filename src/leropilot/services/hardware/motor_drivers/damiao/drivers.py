"""
Damiao CAN bus motor driver implementation.

Supports Damiao motors over CAN bus:
- 4310 (DM4310) - Wrist motors
- 4340 / 4340P (DM4340, DM4340P) - Elbow and shoulder rotation motors
- 8009 / 8009P (DM8009, DM8009P) - Shoulder motors (high torque)
- DM6006, DM8006, DM10054 - Other variants

Based on Hugging Face lerobot implementation with MIT-style control protocol.
Uses python-can library for CAN communication.
"""

import logging
import time
from typing import Any

import can

from leropilot.models.hardware import MotorModelInfo, MotorTelemetry

from ..base import BaseMotorDriver
from .tables import (
    DAMAIO_MODELS_LIST,
    DamiaoConstants,
    select_model_for_number,
)

logger = logging.getLogger(__name__)


def float_to_uint(x: float, x_min: float, x_max: float, bits: int) -> int:
    """Convert float to unsigned int for CAN protocol encoding."""
    span = x_max - x_min
    x_clipped = min(max(x, x_min), x_max)
    return int((x_clipped - x_min) * ((1 << bits) - 1) / span)


def uint_to_float(x_int: int, x_min: float, x_max: float, bits: int) -> float:
    """Convert unsigned int to float for CAN protocol decoding."""
    span = x_max - x_min
    return float(x_int) * span / ((1 << bits) - 1) + x_min


class DamiaoCAN_Driver(BaseMotorDriver[tuple[int, int]]):
    """Driver for Damiao CAN bus motors using MIT control protocol"""

    def __init__(self, interface: str, baud_rate: int | None = None) -> None:
        """
        Initialize Damiao CAN driver.

        Args:
            interface: CAN device ("can0" for socketcan, "COM12" for SLCAN, "PCAN_USBBUS1" for PCAN)
            baud_rate: CAN baud rate (default: 1000000)
        """
        super().__init__(interface, baud_rate or DamiaoConstants.DEFAULT_BAUDRATE)
        self.bus: Any = None
        self.motors: dict[tuple[int, int], dict[str, Any]] = {}  # (send, recv) -> state dict

    def _get_motor_limits(self, motor_id: tuple[int, int]) -> tuple[float, float, float]:
        """Get (pmax, vmax, tmax) for a motor, using cached model info if available."""
        motor_info = self.motors.get(motor_id, {}).get("model_info")
        model_name = motor_info.variant if motor_info else "DM4310"
        return DamiaoConstants.MOTOR_LIMIT_PARAMS.get(model_name, (12.5, 45.0, 18.0))

    def connect(self) -> bool:
        """Connect to CAN bus"""
        if self.connected and self.bus:
            return True

        try:
            # Parse interface: "type:channel"
            if ":" in self.interface:
                bustype, channel = self.interface.split(":", 1)
            else:
                # Backward compatibility: infer from channel name
                channel = self.interface
                if self.interface.startswith("COM") or self.interface.startswith("/dev/tty"):
                    bustype = "slcan"
                elif self.interface.startswith("can"):
                    bustype = "socketcan"
                elif self.interface.startswith("PCAN_"):
                    bustype = "pcan"
                else:
                    bustype = "socketcan"  # Default

            # PCAN specific: if re-connecting rapidly, wait for driver to settle
            if bustype == "pcan":
                time.sleep(0.5)  # Increased for PCAN-USB Pro FD

            logger.debug(f"Connecting to CAN bus: {channel} (type: {bustype})")

            # For PCAN FD adapters on Windows, we try to be compatible.
            # python-can't pcan backend handles bitrate but we ensure it's not blocked by
            # leftover FD configurations.
            try:
                self.bus = can.interface.Bus(channel=channel, bustype=bustype, bitrate=self.baud_rate)
            except Exception as e:
                if "current configuration" in str(e).lower():
                    logger.error(
                        "PCAN Access Denied: Please ensure PCAN-View or other CAN tools "
                        f"are CLOSED. Error: {e}"
                    )
                raise e

            self.connected = True
            logger.debug(f"Connected to Damiao CAN bus on {self.interface}")
            return True

        except Exception as e:
            logger.error(f"Failed to connect to Damiao CAN bus: {e}")
            self.connected = False
            return False

    def disconnect(self) -> bool:
        """Disconnect from CAN bus"""
        try:
            if self.bus:
                self.bus.shutdown()
                # PCAN/Windows driver needs a solid moment to release hardware
                if self.interface.startswith("PCAN_") or ":PCAN_" in self.interface:
                    time.sleep(0.3)
            self.connected = False
            logger.debug("Disconnected from Damiao CAN bus")
            return True
        except Exception as e:
            logger.error(f"Error disconnecting: {e}")
            return False

    def _encode_mit_cmd(
        self,
        pos: float,
        vel: float,
        torq: float,
        kp: float,
        kd: float,
        pmax: float = 12.5,
        vmax: float = 45.0,
        tmax: float = 18.0,
    ) -> bytes:
        """Encode MIT control command into 8-byte CAN frame using provided limits"""
        pos_u = float_to_uint(pos, -pmax, pmax, 16)
        vel_u = float_to_uint(vel, -vmax, vmax, 12)
        kp_u = float_to_uint(kp, 0.0, 500.0, 12)  # KP limits are fixed
        kd_u = float_to_uint(kd, 0.0, 5.0, 12)  # KD limits are fixed
        torq_u = float_to_uint(torq, -tmax, tmax, 12)

        return bytes(
            [
                (pos_u >> 8) & 0xFF,
                pos_u & 0xFF,
                (vel_u >> 4) & 0xFF,
                ((vel_u & 0xF) << 4) | ((kp_u >> 8) & 0xF),
                kp_u & 0xFF,
                (kd_u >> 4) & 0xFF,
                ((kd_u & 0xF) << 4) | ((torq_u >> 8) & 0xF),
                torq_u & 0xFF,
            ]
        )

    def _send_can_frame(self, motor_id: int | tuple[int, int], data: bytes) -> bool:
        """Send CAN frame to motor.

        motor_id may be an int (send/recv ID) or a tuple (send_id, recv_id). When
        a tuple is provided, the first element is used as the arbitration id to send.
        """
        if not self.bus or not self.connected:
            return False

        try:
            if isinstance(motor_id, (list, tuple)):
                arb = int(motor_id[0])
            else:
                arb = int(motor_id)

            msg = can.Message(arbitration_id=arb, data=data, is_extended_id=False)
            self.bus.send(msg)
            return True
        except Exception as e:
            logger.error(f"Error sending CAN message to motor {motor_id}: {e}")
            return False

    def _recv_motor_response(
        self, expected_id: int | tuple[int, int] | None = None, timeout: float = 0.1
    ) -> can.Message | None:
        """Receive response from motor.

        Accept messages by either matching the reply arbitration ID or by
        recognizing the motor's send ID in data[0]. `expected_id` may be an
        int (send/recv same) or a tuple (send_id, recv_id).
        """
        if not self.bus:
            return None

        deadline = time.time() + timeout
        try:
            while time.time() < deadline:
                remaining = max(0.0, deadline - time.time())
                msg = self.bus.recv(timeout=min(0.05, remaining))
                if not msg:
                    continue

                # If no expected_id specified, return the first message seen
                if expected_id is None:
                    return msg

                # Normalize expected ids
                if isinstance(expected_id, (list, tuple)):
                    send_id = int(expected_id[0])
                    recv_id = int(expected_id[1])
                else:
                    send_id = int(expected_id)
                    recv_id = int(expected_id)

                # Match by reply arbitration id
                if msg.arbitration_id == recv_id:
                    return msg

                # Match by payload first byte indicating source motor id
                try:
                    if msg.data and len(msg.data) >= 1 and (msg.data[0] & 0xFF) == (send_id & 0xFF):
                        return msg
                except Exception:
                    pass

            return None
        except Exception as e:
            logger.debug(f"Error receiving CAN message: {e}")
            return None

    def _decode_motor_state(
        self, data: bytes, pmax: float = 12.5, vmax: float = 45.0, tmax: float = 18.0
    ) -> tuple[float, float, float, int, int]:
        """Decode motor state from CAN data using provided or default limits"""
        if len(data) < 8:
            raise ValueError("Invalid motor state data")

        # Extract encoded values
        pos_u = (data[1] << 8) | data[2]
        vel_u = (data[3] << 4) | (data[4] >> 4)
        torq_u = ((data[4] & 0x0F) << 8) | data[5]
        temp_mos = data[6]
        temp_rotor = data[7]

        # Decode to physical values
        position = uint_to_float(pos_u, -pmax, pmax, 16)
        velocity = uint_to_float(vel_u, -vmax, vmax, 12)
        torque = uint_to_float(torq_u, -tmax, tmax, 12)

        return position, velocity, torque, temp_mos, temp_rotor

    def ping_motor(self, motor_id: tuple[int, int]) -> bool:
        """Ping motor by sending refresh command and checking for response.

        `motor_id` must be a `(send_id, recv_id)` tuple for Damiao CAN motors.
        """
        try:
            # Normalize motor id tuple
            send_id = int(motor_id[0])

            # Send refresh command to motor ID (not PARAM_ID)
            # Format: [motor_id_low, motor_id_high, CMD_REFRESH, 0, 0, 0, 0, 0]
            refresh_data = bytes([send_id & 0xFF, (send_id >> 8) & 0xFF, DamiaoConstants.CMD_REFRESH, 0, 0, 0, 0, 0])

            # Send to motor ID (use send_id for arbitration)
            if not self._send_can_frame(motor_id, refresh_data):
                return False

            # Wait for response (30ms)
            response = self._recv_motor_response(expected_id=motor_id, timeout=0.03)
            if response and len(response.data) >= 8:
                self.motors[motor_id] = {"last_seen": time.time(), "state": self._decode_motor_state(response.data)}
                return True
            return False
        except Exception as e:
            logger.debug(f"Ping exception for motor {motor_id}: {e}")
            return False

    def identify_model(
        self,
        motor_id: tuple[int, int],
        model_number: int | None = None,
        fw_major: int | None = None,
        fw_minor: int | None = None,
        raise_on_ambiguous: bool = False,
    ) -> MotorModelInfo:
        """Identify motor model by reading model number parameter

        `motor_id` must be a tuple `(send_id, recv_id)`; callers who only have
        a send id can pass `(send_id, send_id)` as a temporary form during scanning.
        """
        try:
            # Try to read model number from motor parameter
            # Address 0x01 is the standard model number address for Damiao motors
            model_param_addrs = [0x01, 0x00, 0x100]  # Prioritize 0x01

            for param_addr in model_param_addrs:
                # Add a tiny delay between parameter reads to ensure motor can process
                if param_addr != model_param_addrs[0]:
                    time.sleep(0.01)

                model_num = self.read_parameter(motor_id, param_addr)
                if model_num is not None and model_num > 0:
                    model_info = select_model_for_number(model_num)
                    if model_info:
                        logger.debug(f"Identified motor {motor_id} as {model_info.model} (model_num: {model_num})")
                        # Cache the model info for future limit lookups
                        if motor_id not in self.motors:
                            self.motors[motor_id] = {}
                        self.motors[motor_id]["model_info"] = model_info
                        return model_info
                    else:
                        logger.warning(
                            f"Motor {motor_id} returned unknown model number: {model_num} "
                            f"(hex: {hex(model_num)}) at address {hex(param_addr)}"
                        )

            # Fallback to provided model_number if available
            if model_number is not None:
                mi = select_model_for_number(model_number)
                if mi is None:
                    raise ValueError(f"Unknown Damiao model number: {model_number}")
                return mi

            # Could not determine model -> raise
            raise ValueError(
                f"Unable to identify Damiao motor model for {motor_id} "
                "(read failed or model mapping missing)"
            )

        except Exception as e:
            if raise_on_ambiguous:
                logger.error(f"Error identifying motor {motor_id}: {e}")
                raise
            else:
                logger.warning(f"Identification failed for motor {motor_id}: {e}")
                raise

    def supported_models(self) -> list[MotorModelInfo]:
        """Return list of supported Damiao models"""
        return DAMAIO_MODELS_LIST.copy()

    def scan_motors(self, scan_range: list[int] | None = None) -> dict[tuple[int, int], MotorModelInfo]:
        """Scan CAN bus and discover all Damiao motors.

        During scanning we record discovered `recv` arbitration IDs and avoid
        sending frames to those IDs later in the scan (they are receive-only
        addresses for already-discovered motors). When we can determine a
        distinct recv id we return a mapping of `(send, recv)` -> `MotorModelInfo`.
        """
        if scan_range is None:
            scan_range = list(range(1, 128))  # Default: 1-127

        discovered: dict[tuple[int, int], MotorModelInfo] = {}
        discovered_recv_ids: set[int] = set()
        logger.info(f"Scanning {len(scan_range)} motor IDs on Damiao CAN bus")

        # Scan in smaller batches to avoid overwhelming the bus
        batch_size = 10
        for i in range(0, len(scan_range), batch_size):
            # Abort early if the bus has entered an error state (e.g. wrong bitrate)
            try:
                # can.BusState: ACTIVE=0, PASSIVE=1, ERROR=2, OFF=3
                if hasattr(self.bus, "state") and self.bus.state in (can.BusState.PASSIVE, can.BusState.OFF):
                    # If we haven't found anything yet, passive state strongly suggests wrong bitrate
                    if not discovered and i >= batch_size:
                        logger.warning(
                            f"Aborting Damiao scan: Bus is in {self.bus.state.name} "
                            "state (likely incorrect bitrate)"
                        )
                        break
            except Exception:
                pass

            batch = scan_range[i : i + batch_size]
            logger.debug(f"Scanning batch: {batch}")

            for send_id in batch:
                # If this send_id was previously observed as a recv id for another
                # motor, skip sending to it (it's a receive-only address)
                if send_id in discovered_recv_ids:
                    logger.debug(f"Skipping {send_id} because it was observed as a recv ID earlier")
                    continue

                # Send refresh (probe) using the send arbitration id (int)
                refresh_data = bytes(
                    [send_id & 0xFF, (send_id >> 8) & 0xFF, DamiaoConstants.CMD_REFRESH, 0, 0, 0, 0, 0]
                )

                # Send refresh (probe) using the send arbitration id (int)
                refresh_data = bytes(
                    [send_id & 0xFF, (send_id >> 8) & 0xFF, DamiaoConstants.CMD_REFRESH, 0, 0, 0, 0, 0]
                )

                if not self._send_can_frame(send_id, refresh_data):
                    continue

                # Use a moderate timeout for discovery (30ms is a safe balance)
                response = self._recv_motor_response(expected_id=None, timeout=0.03)
                if not response or not response.data:
                    continue

                # If reply came from a different arbitration id, and it includes the
                # original send id in data[0], treat that arbitration id as the recv id
                recv_id: int | None = None
                try:
                    if (
                        response.arbitration_id != send_id
                        and len(response.data) >= 1
                        and (response.data[0] & 0xFF) == (send_id & 0xFF)
                    ):
                        recv_id = int(response.arbitration_id)
                        discovered_recv_ids.add(recv_id)
                    elif response.arbitration_id == send_id:
                        # If the payload's first byte doesn't match the send id, that
                        # suggests we accidentally sent to a recv id or saw unrelated
                        # traffic. Treat the probed id as a recv id and skip it.
                        if len(response.data) >= 1 and (response.data[0] & 0xFF) != (send_id & 0xFF):
                            logger.debug(
                                "Probed id %s appears to be a recv-id (payload indicates different source); skipping",
                                send_id,
                            )
                            discovered_recv_ids.add(send_id)
                            continue
                        recv_id = send_id
                    else:
                        # If we got a frame that doesn't match the expected pattern but
                        # contains a different source id in data[0], this likely means
                        # we accidentally sent to a recv id: mark this send_id as a
                        # recv id and skip it going forward.
                        if len(response.data) >= 1:
                            logger.debug(
                                "Received unexpected frame when probing %s; marking %s as recv-id and skipping",
                                send_id,
                                send_id,
                            )
                            discovered_recv_ids.add(send_id)
                        continue
                except Exception:
                    continue

                # For Damiao, we accept both distinct and identical send/recv IDs.
                # Many standard configurations use the same arbitration ID for both directions.
                if recv_id is None:
                    logger.debug(f"Skipping send id {send_id}: no response arbitration ID discovered")
                    continue

                id_tuple = (send_id, recv_id)
                try:
                    # During discovery, we don't want to crash the whole scan if one motor fails to identify
                    model_info = self.identify_model(id_tuple, raise_on_ambiguous=False)
                    from typing import cast

                    discovered[id_tuple] = cast(MotorModelInfo, model_info)
                except Exception as e:
                    logger.warning(f"Failed to identify motor {id_tuple}, skipping: {e}")
                    continue

                logger.info("Found motor send=%s recv=%s (%s)", send_id, recv_id, discovered[id_tuple].model)

            # Small delay between batches to let bus recover
            if i + batch_size < len(scan_range):
                time.sleep(0.01)

        logger.info(f"Scan complete: found {len(discovered)} motors")
        return discovered

    def read_telemetry(self, motor_id: tuple[int, int]) -> MotorTelemetry | None:
        """Read real-time telemetry from a single motor

        `motor_id` is a tuple `(send_id, recv_id)`. `MotorTelemetry.id` will be
        populated with the logical send id (int) for compatibility with callers.
        """
        try:
            # Normalize send id
            send_id = int(motor_id[0])

            # Send refresh command to motor ID (not PARAM_ID)
            refresh_data = bytes([send_id & 0xFF, (send_id >> 8) & 0xFF, DamiaoConstants.CMD_REFRESH, 0, 0, 0, 0, 0])

            if not self._send_can_frame(motor_id, refresh_data):
                return None

            # Read response (30ms)
            response = self._recv_motor_response(expected_id=motor_id, timeout=0.03)
            if not response or len(response.data) < 8:
                return None

            # Get limits for this specific motor
            pmax, vmax, tmax = self._get_motor_limits(motor_id)
            position, velocity, torque, temp_mos, temp_rotor = self._decode_motor_state(
                response.data, pmax=pmax, vmax=vmax, tmax=tmax
            )

            if motor_id not in self.motors:
                self.motors[motor_id] = {}

            self.motors[motor_id].update({
                "last_seen": time.time(),
                "state": (position, velocity, torque, temp_mos, temp_rotor),
            })

            return MotorTelemetry(
                id=send_id,
                position=int(position * 1000),  # Convert to milli-radians for compatibility
                velocity=int(velocity * 1000),  # Convert to milli-rad/s
                current=int(torque * 1000),  # Approximate current from torque
                load=0,  # Not available
                voltage=24.0,  # Typical voltage
                temperature=temp_rotor,
                moving=abs(velocity) > 0.01,
                goal_position=0.0,
                error=0,
            )
        except Exception as e:
            logger.error(f"Failed to read telemetry from motor {motor_id}: {e}")
            return None

    def read_bulk_telemetry(self, motor_ids: list[tuple[int, int]]) -> dict[tuple[int, int], MotorTelemetry]:
        """Read telemetry from multiple motors efficiently

        Accepts a list of MotorID tuples and returns a dict keyed by the same tuple ids.
        """
        result: dict[tuple[int, int], MotorTelemetry] = {}
        for mid in motor_ids:
            telemetry = self.read_telemetry(mid)
            if telemetry:
                result[mid] = telemetry
        return result

    def set_position(self, motor_id: tuple[int, int], position: int, speed: int | None = None) -> bool:
        """Set motor target position using MIT control mode

        `motor_id` must be a tuple `(send_id, recv_id)`.
        """
        try:
            pos_rad = float(position) / 1000.0

            # Get motor limits
            pmax, vmax, tmax = self._get_motor_limits(motor_id)
            pos_rad = max(-pmax, min(pmax, pos_rad))

            # Use moderate gains for position control
            kp = 50.0
            kd = 1.0

            cmd_data = self._encode_mit_cmd(pos_rad, 0.0, 0.0, kp, kd, pmax=pmax, vmax=vmax, tmax=tmax)
            return self._send_can_frame(motor_id, cmd_data)
        except Exception as e:
            logger.error(f"Failed to set position for motor {motor_id}: {e}")
            return False

    def set_torque(self, motor_id: tuple[int, int], enabled: bool) -> bool:
        """Enable or disable motor torque

        `motor_id` must be a tuple `(send_id, recv_id)`.
        """
        try:
            if enabled:
                data = bytes([0xFF] * 7 + [DamiaoConstants.CMD_ENABLE])
            else:
                data = bytes([0xFF] * 7 + [DamiaoConstants.CMD_DISABLE])

            result = self._send_can_frame(motor_id, data)
            logger.debug(f"Set motor {motor_id} torque to {enabled}")
            return result
        except Exception as e:
            logger.error(f"Failed to set torque for motor {motor_id}: {e}")
            return False

    def reboot_motor(self, motor_id: tuple[int, int]) -> bool:
        """Reboot motor - not supported by Damiao protocol

        Accepts MotorID tuple `(send_id, recv_id)` for compatibility with base class.
        """
        logger.warning("Damiao motors do not support reboot command")
        return False

    def bulk_set_torque(self, motor_ids: list[tuple[int, int]], enabled: bool) -> bool:
        """Set torque for multiple motors at once

        `motor_ids` should be a list of `(send_id, recv_id)` tuples.
        """
        try:
            success = True
            for motor_id in motor_ids:
                if not self.set_torque(motor_id, enabled):
                    success = False
            return success
        except Exception as e:
            logger.error(f"Failed to bulk set torque: {e}")
            return False

    def read_parameter(self, motor_id: tuple[int, int], param_addr: int) -> int | None:
        """Read parameter from motor using CAN_CMD_QUERY_PARAM

        `motor_id` must be a `(send_id, recv_id)` tuple. The query is sent using the
        `send_id` (first element of the tuple).
        """
        try:
            # Normalize send id
            send_id = int(motor_id[0])
            # Format: [motor_id_low, motor_id_high, CMD_QUERY_PARAM, param_addr_low, param_addr_high, 0, 0, 0]
            query_data = bytes(
                [
                    send_id & 0xFF,
                    (send_id >> 8) & 0xFF,
                    DamiaoConstants.CAN_CMD_QUERY_PARAM,
                    param_addr & 0xFF,
                    (param_addr >> 8) & 0xFF,
                    0,
                    0,
                    0,
                ]
            )

            # Send query to parameter ID (0x7FF)
            if not self._send_can_frame(DamiaoConstants.PARAM_ID, query_data):
                return None

            # Wait for response from motor (100ms for parameter reads)
            response = self._recv_motor_response(expected_id=motor_id, timeout=0.1)
            if not response or len(response.data) < 8:
                return None

            # Parse parameter value from response
            # Response format:
            #   [motor_id_low, motor_id_high, CMD_QUERY_PARAM,
            #    param_addr_low, param_addr_high, value_low, value_high, 0]
            if response.data[2] != DamiaoConstants.CAN_CMD_QUERY_PARAM:
                return None

            param_value = (response.data[6] << 8) | response.data[5]  # value_high, value_low
            return param_value

        except Exception as e:
            logger.error(f"Failed to read parameter {param_addr} from motor {motor_id}: {e}")
            return None

    def write_parameter(self, motor_id: tuple[int, int], param_addr: int, value: int) -> bool:
        """Write parameter to motor using CAN_CMD_WRITE_PARAM

        `motor_id` must be a `(send_id, recv_id)` tuple. The write is sent using
        the `send_id` (first element of the tuple).
        """
        try:
            send_id = int(motor_id[0])
            # Format (bytes): [motor_id_low, motor_id_high, CMD_WRITE_PARAM, param_addr_low, param_addr_high,
            #                value_low, value_high, 0]
            write_data = bytes(
                [
                    send_id & 0xFF,
                    (send_id >> 8) & 0xFF,
                    DamiaoConstants.CAN_CMD_WRITE_PARAM,
                    param_addr & 0xFF,
                    (param_addr >> 8) & 0xFF,
                    value & 0xFF,
                    (value >> 8) & 0xFF,
                    0,
                ]
            )

            # Send write command to parameter ID (0x7FF)
            if not self._send_can_frame(DamiaoConstants.PARAM_ID, write_data):
                return False

            # Wait for acknowledgment (optional - some implementations may not respond)
            response = self._recv_motor_response(expected_id=motor_id, timeout=0.1)
            if response and len(response.data) >= 3:
                # Check if response acknowledges the write command
                if response.data[2] == DamiaoConstants.CAN_CMD_WRITE_PARAM:
                    return True

            # If no response or timeout, assume success (common for write operations)
            logger.debug(f"Parameter {param_addr} written to motor {motor_id} (value: {value})")
            return True

        except Exception as e:
            logger.error(f"Failed to write parameter {param_addr} to motor {motor_id}: {e}")
            return False

    def save_parameters(self, motor_id: tuple[int, int]) -> bool:
        """Save current parameters to motor's non-volatile memory using CAN_CMD_SAVE_PARAM

        `motor_id` must be a `(send_id, recv_id)` tuple; the save command is sent
        using the `send_id` and the acknowledgment is matched by `motor_id`.
        """
        try:
            send_id = int(motor_id[0])
            # Format: [motor_id_low, motor_id_high, CMD_SAVE_PARAM, 0, 0, 0, 0, 0]
            save_data = bytes(
                [send_id & 0xFF, (send_id >> 8) & 0xFF, DamiaoConstants.CAN_CMD_SAVE_PARAM, 0, 0, 0, 0, 0]
            )

            # Send save command to parameter ID (0x7FF)
            if not self._send_can_frame(DamiaoConstants.PARAM_ID, save_data):
                return False

            # Wait for acknowledgment
            response = self._recv_motor_response(expected_id=motor_id, timeout=0.2)
            if response and len(response.data) >= 3:
                # Check if response acknowledges the save command
                if response.data[2] == DamiaoConstants.CAN_CMD_SAVE_PARAM:
                    logger.info(f"Parameters saved to motor {motor_id}")
                    return True

            # If no response, assume success after a delay
            time.sleep(0.1)  # Give motor time to save
            logger.info(f"Parameters save command sent to motor {motor_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to save parameters for motor {motor_id}: {e}")
            return False
