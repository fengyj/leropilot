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
from threading import Event, Thread
from typing import Any

import can

from leropilot.exceptions import OperationalError
from leropilot.models.hardware import MotorModelInfo, MotorTelemetry, PositionType

from ..base import BaseMotorDriver
from .message_cache import MessageCache
from .tables import DAMAIO_MODELS_LIST, DamiaoConstants, DamiaoRegisters, select_model_for_number

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
        # Register-level accessor (centralized access)
        # Local import to avoid cyclical import at module load time
        from .registers import DamiaoRegister

        self.register: DamiaoRegister = DamiaoRegister(self)

        # Message cache for status and parameter responses
        self.cache = MessageCache(max_age=1.0)
        # Cache for last set goal position (raw units)
        self._goal_position_cache: dict[tuple[int, int], float | None] = {}

        # Receive thread for continuous message collection
        self._recv_thread: Thread | None = None
        self._recv_stop_event = Event()
        self._recv_pause_event = Event()  # 临时暂停
        self._recv_pause_event.set()  # 默认不暂停

        # Motor ID registry: maps recv_id -> motor_id and can_id -> motor_id
        # Populated when motors are registered/used
        self._recv_id_map: dict[int, tuple[int, int]] = {}  # recv_id -> (send_id, recv_id)
        self._can_id_map: dict[int, tuple[int, int]] = {}  # can_id -> (send_id, recv_id)

        # Per-motor runtime state is not stored by this driver; callers provide `model_info` when needed.

    def connect(self) -> None:
        """Connect to CAN bus.

        Raises:
            OperationalError: If connection fails.
        """
        if self.connected and self.bus:
            return

        try:
            # Parse interface: "type:channel"
            if ":" in self.interface:
                bustype, channel = self.interface.split(":", 1)
            else:
                raise ValueError(f"Interface must be in format 'type:channel', got: {self.interface}")

            # PCAN specific: if re-connecting rapidly, wait for driver to settle
            if bustype == "pcan":
                time.sleep(0.5)  # Increased for PCAN-USB Pro FD

            logger.debug(f"Connecting to CAN bus: {channel} (type: {bustype})")

            try:
                self.bus = can.interface.Bus(channel=channel, bustype=bustype, bitrate=self.baud_rate)
            except Exception as e:
                if "current configuration" in str(e).lower():
                    logger.error(
                        f"PCAN Access Denied: Please ensure PCAN-View or other CAN tools are CLOSED. Error: {e}"
                    )
                raise e

            self.connected = True
            logger.debug(f"Connected to Damiao CAN bus on {self.interface}")

            self._goal_position_cache.clear()

            # Start receive thread for message caching
            self._recv_stop_event.clear()
            self._recv_thread = Thread(target=self._receive_loop, daemon=True, name="DamiaoCAN-Recv")
            self._recv_thread.start()
            logger.debug("Started CAN message receive thread")

        except Exception as e:
            logger.error(f"Failed to connect to Damiao CAN bus: {e}")
            self.connected = False
            raise OperationalError(
                i18n_key="hardware.motor_device.connect_failed",
                retriable=True,
                interface=self.interface,
            ) from e

    def disconnect(self) -> bool:
        """Disconnect from CAN bus"""
        try:
            # Stop receive thread first
            if self._recv_thread and self._recv_thread.is_alive():
                logger.debug("Stopping receive thread...")
                self._recv_stop_event.set()
                self._recv_thread.join(timeout=2.0)
                if self._recv_thread.is_alive():
                    logger.warning("Receive thread did not stop gracefully")
                else:
                    logger.debug("Receive thread stopped")

            # Clear message cache
            self.cache.clear()

            # Shutdown CAN bus
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

    def _register_motor_id(self, motor_id: tuple[int, int]) -> None:
        """Register a motor ID for message routing.

        Populates internal maps used by receive thread to classify messages.
        Should be called when a motor is added to the system.

        Args:
            motor_id: Motor identifier (send_id, recv_id)
        """
        send_id, recv_id = motor_id
        self._recv_id_map[recv_id] = motor_id
        # CAN ID is lower 8 bits of send_id (CANID_L)
        can_id = send_id & 0xFF
        self._can_id_map[can_id] = motor_id

    def _receive_loop(self) -> None:
        """Receive thread main loop.

        Continuously receives CAN messages and caches them by type.
        Runs until disconnect sets stop event.
        """
        logger.debug("CAN receive loop started")
        try:
            while not self._recv_stop_event.is_set():
                try:
                    self._recv_pause_event.wait()  # 等待未暂停
                    # Short timeout to allow checking stop event frequently
                    msg = self.bus.recv(timeout=0.05)
                    if not msg:
                        continue

                    # Classify and cache the message
                    self._classify_and_cache(msg)

                except Exception as e:
                    # Log errors but keep running unless stopping
                    if not self._recv_stop_event.is_set():
                        logger.warning(f"Error in receive loop: {e}")

        except Exception as e:
            logger.error(f"Fatal error in receive loop: {e}", exc_info=True)
        finally:
            logger.debug("CAN receive loop stopped")

    def _classify_and_cache(self, msg: can.Message) -> None:
        """Classify CAN message by type and cache appropriately.

        Message types:
        1. Status feedback (MST_ID): Position, velocity, torque, temps
        2. Parameter response (0x7FF): Read/write parameter responses

        Args:
            msg: CAN message from bus
        """
        arb_id = msg.arbitration_id
        data = msg.data

        # Minimum message length check
        if not data or len(data) < 2:
            return

        # Extract motor CAN ID from data (CANID_L | CANID_H)
        motor_can_id = data[0] | (data[1] << 8)

        # Classify by arbitration ID
        if arb_id == 0x7FF:
            # Parameter message (read/write response)
            self._cache_parameter_message(motor_can_id, data, arb_id)
        else:
            # Status feedback message (from recv_id)
            self._cache_status_message(arb_id, data)

    def _cache_status_message(self, recv_id: int, data: bytes) -> None:
        """Cache motor status feedback message.

        Args:
            recv_id: CAN arbitration ID (should match motor recv_id)
            data: 8-byte CAN data
        """
        # Look up motor_id from recv_id
        motor_id = self._recv_id_map.get(recv_id)
        if motor_id:
            self.cache.update_status(motor_id, data, recv_id)
        else:
            # Unknown motor - could be a new motor or noise
            logger.debug(f"Received status from unregistered motor: recv_id={recv_id:#x}")

    def _cache_parameter_message(self, motor_can_id: int, data: bytes, arb_id: int) -> None:
        """Cache parameter read/write response message.

        Args:
            motor_can_id: Motor CAN ID from data[0:2]
            data: 8-byte CAN data
            arb_id: CAN arbitration ID (0x7FF)
        """
        if len(data) < 4:
            return

        cmd_type = data[2]

        if cmd_type == 0x33:
            # Read parameter response: CANID_L | CANID_H | 0x33 | RID | data[4 bytes]
            register_id = data[3]
            motor_id = self._can_id_to_motor_id(motor_can_id)
            if motor_id:
                self.cache.update_parameter(motor_id, register_id, data, arb_id)
                logger.debug(f"Cached parameter read: motor={motor_id}, reg={register_id:#x}")

        elif cmd_type == 0x55:
            # Write parameter confirmation: CANID_L | CANID_H | 0x55 | RID
            register_id = data[3]
            motor_id = self._can_id_to_motor_id(motor_can_id)
            if motor_id:
                self.cache.update_parameter(motor_id, register_id, data, arb_id)
                logger.debug(f"Cached parameter write confirmation: motor={motor_id}, reg={register_id:#x}")

        elif cmd_type == 0xAA:
            # Store parameter confirmation: CANID_L | CANID_H | 0xAA | 0x01
            # Could log or track, but typically no action needed
            motor_id = self._can_id_to_motor_id(motor_can_id)
            logger.debug(f"Parameter stored to flash: motor={motor_id}")

    def _can_id_to_motor_id(self, can_id: int) -> tuple[int, int] | None:
        """Convert CAN ID to motor_id.

        Args:
            can_id: CAN ID from message data (CANID_L | CANID_H << 8)

        Returns:
            motor_id (send_id, recv_id) if registered, None otherwise
        """
        # Try direct lookup by lower 8 bits
        motor_id = self._can_id_map.get(can_id & 0xFF)
        if motor_id:
            return motor_id

        # Try full 16-bit CAN ID
        motor_id = self._can_id_map.get(can_id)
        if motor_id:
            return motor_id

        logger.debug(f"Unknown motor CAN ID: {can_id:#x}")
        return None

    def send_can_frame(self, motor_id: tuple[int, int], data: bytes, motor_can_id: int | None = None) -> None:
        """Send a raw CAN frame using the driver's bus.

        `send_id` is used as the CAN arbitration id for outgoing frames.
        Returns True on success or raises :class:`OperationalError` on send failure.
        """
        try:
            self._register_motor_id(motor_id)
            send_id = int(motor_can_id if motor_can_id is not None else motor_id[0])
            msg = can.Message(arbitration_id=int(send_id), data=data, is_extended_id=False)
            self.bus.send(msg)
        except Exception as e:
            raise OperationalError(
                i18n_key="hardware.motor_device.send_failed", retriable=True, motor_id=motor_id
            ) from e

    def recv_motor_response(self, expected_id: tuple[int, int], timeout: float = 0.1) -> can.Message:
        """Receive response message matching `expected_id` or payload source byte.

        `expected_id` may be None (return first message), or a (send_id, recv_id) tuple.
        Returns `can.Message` or raise TimeoutError on timeout. Raises :class:`OperationalError` on bus errors.
        """
        deadline = time.time() + timeout
        try:
            while time.time() < deadline:
                remaining = max(0.0, deadline - time.time())
                msg = self.bus.recv(timeout=min(0.05, remaining))
                if not msg:
                    continue

                send_id = int(expected_id[0])
                recv_id = int(expected_id[1])

                # Match by reply arbitration id
                if msg.arbitration_id == recv_id:
                    return msg

                # Match by payload first byte indicating source motor id

                if msg.data and len(msg.data) == 8 and (msg.data[0] & 0xFF) == (send_id & 0xFF):
                    return msg
            raise TimeoutError()
        except Exception as e:
            raise OperationalError(i18n_key="hardware.motor_device.recv_failed", retriable=True) from e

    def read_parameter(
        self, motor_id: tuple[int, int], param_addr: int, timeout: float = 0.1, max_age: float | None = None
    ) -> bytes:
        """Read a 4-byte parameter value from motor using CAN_CMD_QUERY_PARAM.

        Returns: 4 bytes (little-endian representation) or None on timeout/malformed response.
        Raises OperationalError for bus-level errors.
        """

        try:
            response_data = self.cache.get_parameter_raw(motor_id, param_addr, max_age)
            if response_data is None:
                send_id = int(motor_id[0])
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

                self.send_can_frame(motor_id, query_data, DamiaoConstants.PARAM_ID)
                if self.cache.wait_for_parameter(motor_id, param_addr, timeout=timeout):
                    response_data = self.cache.get_parameter_raw(motor_id, param_addr)
                    if response_data is None:
                        raise OperationalError(
                            i18n_key="hardware.motor_device.malformed_response",
                            retriable=True,
                            motor_id=motor_id,
                            param_addr=param_addr,
                        )
                else:
                    raise OperationalError(
                        i18n_key="hardware.motor_device.param_response_timeout",
                        retriable=True,
                        motor_id=motor_id,
                        param_addr=param_addr,
                    )

            if len(response_data) < 8:
                raise OperationalError(
                    i18n_key="hardware.motor_device.malformed_response",
                    retriable=True,
                    motor_id=motor_id,
                    param_addr=param_addr,
                )

            # Expect response payload: data[2] == CMD (0x33 for query)
            if response_data[2] != DamiaoConstants.CAN_CMD_QUERY_PARAM:
                raise OperationalError(
                    i18n_key="hardware.motor_device.unexpected_response",
                    retriable=True,
                    motor_id=motor_id,
                    param_addr=param_addr,
                )

            # Value bytes are stored in data[4:8] (little-endian)
            return response_data[4:8]
        except OperationalError:
            raise
        except Exception as e:
            raise OperationalError(
                i18n_key="hardware.motor_device.read_param_failed",
                retriable=True,
                motor_id=motor_id,
                param_addr=param_addr,
            ) from e

    def bulk_read_parameters(
        self,
        motor_id_and_params: list[tuple[tuple[int, int], int]],
        base_timeout: float = 0.1,
        max_age: float | None = None,
    ) -> dict[tuple[tuple[int, int], int], bytes]:
        """Bulk read multiple parameters from multiple motors.

        Args:
            motor_id_and_params: List of (motor_id, param_addr) tuples to read.
            base_timeout: Base timeout per parameter in seconds.
            max_age: Maximum age in seconds for cached data to be considered valid.
        Returns:
            Dict mapping (motor_id, param_addr) to value_bytes for successful reads.
        """
        results: dict[tuple[tuple[int, int], int], bytes] = {}

        start_time = time.time()
        max_wait = base_timeout + (0.005 * len(motor_id_and_params))

        for motor_id, param_addr in motor_id_and_params:
            if (time.time() - start_time) >= max_wait:
                break  # Overall timeout reached
            if (motor_id, param_addr) in results:
                continue  # Already read
            wait_list: list[tuple[tuple[int, int], int]] = []
            response_data = self.cache.get_parameter_raw(motor_id, param_addr, max_age)
            if response_data is None:
                try:
                    send_id = int(motor_id[0])
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

                    self.send_can_frame(motor_id, query_data, DamiaoConstants.PARAM_ID)
                    wait_list.append((motor_id, param_addr))
                except OperationalError as e:
                    logger.warning(f"Bulk read parameter send failed for motor {motor_id}, param {param_addr:#x}: {e}")
                    continue
            else:
                results[(motor_id, param_addr)] = response_data[4:8]
            if wait_list:
                for motor_id_w, param_addr_w in wait_list:
                    self.cache.wait_for_parameter(motor_id_w, param_addr_w, timeout=base_timeout)

        if len(results) < len(motor_id_and_params):
            raise OperationalError(
                i18n_key="hardware.motor_device.bulk_param_response_timeout",
                retriable=True,
            )
        return results

    def write_parameter(self, motor_id: tuple[int, int], param_addr: int, value_bytes: bytes) -> None:
        """Write a 4-byte parameter value to `param_addr`.

        `value_bytes` must be 4 bytes (little-endian representation).
        Raises OperationalError on errors.
        """
        # Prevent writes to read-only registers
        if self.register.is_read_only(param_addr):
            raise OperationalError(
                i18n_key="hardware.motor_device.write_ro_register",
                retriable=False,
                motor_id=motor_id,
                param_addr=param_addr,
            )

        if not isinstance(value_bytes, (bytes, bytearray)) or len(value_bytes) != 4:
            raise ValueError("value_bytes must be exactly 4 bytes")

        try:
            send_id = int(motor_id[0])

            write_data = bytes(
                [
                    send_id & 0xFF,
                    (send_id >> 8) & 0xFF,
                    DamiaoConstants.CAN_CMD_WRITE_PARAM,
                    param_addr & 0xFF,
                    (param_addr >> 8) & 0xFF,
                ]
            ) + bytes(value_bytes)

            self.send_can_frame(motor_id, write_data, DamiaoConstants.PARAM_ID)
            if not self.cache.wait_for_parameter(motor_id, param_addr, timeout=0.1):
                raise OperationalError(
                    i18n_key="hardware.motor_device.param_response_timeout",
                    retriable=True,
                    motor_id=motor_id,
                    param_addr=param_addr,
                )

        except OperationalError:
            raise
        except Exception as e:
            raise OperationalError(
                i18n_key="hardware.motor_device.write_param_failed",
                retriable=True,
                motor_id=motor_id,
                param_addr=param_addr,
            ) from e

    def bulk_write_parameters(self, items: list[tuple[tuple[int, int], int, bytes]], base_timeout: float = 0.1) -> None:
        """Bulk write multiple parameters.

        Args:
            items: list of (motor_id, param_addr, value_bytes)
            base_timeout: base timeout used when waiting for confirmations

        Behavior: send all write frames first, then wait for confirmations
        for all items. Raises OperationalError if any confirmation is missing.
        """
        if not items:
            return

        # Send all write frames without waiting
        wait_list: list[tuple[tuple[int, int], int]] = []
        for motor_id, param_addr, value_bytes in items:
            if not isinstance(value_bytes, (bytes, bytearray)) or len(value_bytes) != 4:
                raise ValueError("value_bytes must be exactly 4 bytes")
            if self.register.is_read_only(param_addr):
                raise OperationalError(
                    i18n_key="hardware.motor_device.write_ro_register",
                    retriable=False,
                    motor_id=motor_id,
                    param_addr=param_addr,
                )
            try:
                send_id = int(motor_id[0])
                write_data = bytes(
                    [
                        send_id & 0xFF,
                        (send_id >> 8) & 0xFF,
                        DamiaoConstants.CAN_CMD_WRITE_PARAM,
                        param_addr & 0xFF,
                        (param_addr >> 8) & 0xFF,
                    ]
                ) + bytes(value_bytes)
                self.send_can_frame(motor_id, write_data, DamiaoConstants.PARAM_ID)
                wait_list.append((motor_id, param_addr))
            except OperationalError as e:
                logger.warning(f"Bulk write parameter send failed for motor {motor_id}, param {param_addr:#x}: {e}")

        # Wait for confirmations
        for motor_id_w, param_addr_w in wait_list:
            self.cache.wait_for_parameter(motor_id_w, param_addr_w, timeout=base_timeout)

        # Verify all confirmations received
        missing = [(m, p) for (m, p) in wait_list if self.cache.get_parameter_raw(m, p) is None]
        if missing:
            logger.error(f"Bulk write confirmation missing for {len(missing)} items: {missing}")
            raise OperationalError(i18n_key="hardware.motor_device.bulk_param_write_timeout", retriable=True)
        return None

    def save_parameters(
        self,
        motor_id: tuple[int, int],
        timeout: float = 0.1,
    ) -> None:
        """Send command to save parameters to flash memory.

        存储参数命令:
        报文ID: 0x7FF (STD)
        数据格式: CANID_L | CANID_H | 0xAA | 0x01 | 0x00 | 0x00 | 0x00 | 0x00

        写入成功后, 会返回写入的数据, 帧格式与发送的相同.

        注意:
        1. 存储参数只在失能模式下生效
        2. 存储参数时会一次性保留全部参数
        3. 该操作将参数写入片内flash中, 每次操作时间最大为30ms, 请注意留足够的时间
        4. flash擦写次数约1万次, 请不要频繁发送"存储参数"指令

        Args:
            motor_id: Motor identifier (send_id, recv_id)
            timeout: Timeout for confirmation response

        Raises:
            OperationalError: On send failure or timeout
        """
        try:
            send_id = motor_id[0]

            # 数据格式: CANID_L | CANID_H | 0xAA | 0x01 | 0x00...
            cmd_data = bytes(
                [
                    send_id & 0xFF,
                    (send_id >> 8) & 0xFF,
                    0xAA,
                    0x01,
                    0x00,
                    0x00,
                    0x00,
                    0x00,
                ]
            )

            # 发送到 0x7FF
            self.send_can_frame(motor_id, cmd_data, motor_can_id=0x7FF)
            logger.info(f"Sent save parameters command to {motor_id}")

            # 等待确认响应 (可选，根据需求决定是否等待)
            # 接收线程会自动缓存 0xAA 确认消息
            # 如果需要确认，可以等待一小段时间
            time.sleep(timeout)

        except OperationalError:
            raise
        except Exception as e:
            logger.error(f"Failed to send save parameters to {motor_id}: {e}")
            raise OperationalError(
                i18n_key="hardware.motor_device.send_failed", retriable=True, motor_id=motor_id
            ) from e

    def refresh_status(self, motor_id: tuple[int, int]) -> None:
        """Send a refresh command to the motor to request updated status.

        Raises OperationalError on send failure.

        NOTICE: this is not a official Damiao command, but motors respond to it by sending status frames.
        """
        send_id = int(motor_id[0])
        refresh_data = bytes([send_id & 0xFF, (send_id >> 8) & 0xFF, DamiaoConstants.CMD_REFRESH, 0, 0, 0, 0, 0])
        self.send_can_frame(motor_id, refresh_data, DamiaoConstants.PARAM_ID)

    def bulk_refresh_status(self, motors: dict[tuple[int, int], MotorModelInfo]) -> None:
        """Send refresh commands to multiple motors to request updated status.

        Raises OperationalError on send failure.
        """
        for mid in motors.keys():
            self.refresh_status(mid)

    def read_feedback(
        self,
        motor_id: tuple[int, int],
        max_age: float = 1.0,
    ) -> tuple[int, float, float, float, float, float] | None:
        """Read a motor feedback frame and return (state, position, velocity, torque, temp_mos, temp_rotor).

        Raises OperationalError on IO or parsing errors. Uses `self.register.get_pmax_vmax_tmax`
        to obtain pmax/vmax/tmax for decoding; falls back to driver defaults when unavailable.
        """
        data = self.cache.get_status_raw(motor_id, max_age=max_age)
        if data is None:
            return None

        # Extract status/error nibble if present (per documentation ERR encoded in upper nibble of data[1])
        try:
            state = (data[1] >> 4) & 0x0F
        except Exception:
            state = 0

        # Fetch effective limits for decoding
        pmax, vmax, tmax = self.register.get_pmax_vmax_tmax(motor_id)

        try:
            # Inline decode to avoid dependency on _decode_motor_state and ensure types
            pos_u = (data[1] << 8) | data[2]
            vel_u = (data[3] << 4) | (data[4] >> 4)
            torq_u = ((data[4] & 0x0F) << 8) | data[5]
            temp_mos = float(int(data[6]))
            temp_rotor = float(int(data[7]))

            position = uint_to_float(int(pos_u), -pmax, pmax, 16)
            velocity = uint_to_float(int(vel_u), -vmax, vmax, 12)
            torque = uint_to_float(int(torq_u), -tmax, tmax, 12)
        except Exception as e:
            logger.debug(f"Failed to decode feedback frame for {motor_id}: {e}")
            raise OperationalError(
                i18n_key="hardware.motor_device.parse_failed", retriable=False, motor_id=motor_id
            ) from e

        return (int(state), float(position), float(velocity), float(torque), float(temp_mos), float(temp_rotor))

    def send_mit_control(
        self,
        motor_id: tuple[int, int],
        position: float,
        velocity: float,
        torque: float,
        kp: float = 50.0,
        kd: float = 1.0,
    ) -> None:
        """Send a MIT control frame to `motor_id` using register-derived limits.

        All of `position`, `velocity`, and `torque` are required and must be numeric.
        This uses `self.register.get_pmax_vmax_tmax` to obtain pmax/vmax/tmax and
        clamps the provided inputs before encoding. Raises OperationalError on
        send failure.
        """

        # Obtain limits from register (fallback to driver defaults)
        pmax, vmax, tmax = self.register.get_pmax_vmax_tmax(motor_id=motor_id)

        # Clamp
        pos_clamped = max(-pmax, min(pmax, position))
        vel_clamped = max(-vmax, min(vmax, velocity))
        tor_clamped = max(-tmax, min(tmax, torque))

        # Encode and send (inline)
        try:
            pos_u = float_to_uint(pos_clamped, -pmax, pmax, 16)
            vel_u = float_to_uint(vel_clamped, -vmax, vmax, 12)
            kp_u = float_to_uint(kp, 0.0, 500.0, 12)
            kd_u = float_to_uint(kd, 0.0, 5.0, 12)
            torq_u = float_to_uint(tor_clamped, -tmax, tmax, 12)
            cmd = bytes(
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
            self.send_can_frame(motor_id, cmd)
            self._goal_position_cache[motor_id] = pos_clamped
        except OperationalError:
            raise
        except Exception as e:
            logger.error(f"Failed to send MIT control to {motor_id}: {e}")
            raise OperationalError(
                i18n_key="hardware.motor_device.send_failed", retriable=True, motor_id=motor_id
            ) from e

    def send_position_velocity_control(
        self,
        motor_id: tuple[int, int],
        position: float,
        velocity: float,
    ) -> None:
        """Send position-velocity control command (0x100+ID mode).

        控制报文 ID: 0x100+ID
        数据格式: p_des[D0-D3], v_des[D4-D7]

        Args:
            motor_id: Motor identifier (send_id, recv_id)
            position: Target position in radians (浮点型, 低位在前, 高位在后)
            velocity: Target velocity in rad/s, 作为梯形加速度运行下最高速度 (浮点型)

        Raises:
            OperationalError: On send failure
        """
        try:
            # 获取电机限制
            pmax, vmax, _ = self.register.get_pmax_vmax_tmax(motor_id)

            # 限制范围
            pos_clamped = max(-pmax, min(pmax, position))
            vel_clamped = max(-vmax, min(vmax, velocity))

            # 位置和速度都是浮点型, 低位在前, 高位在后
            import struct

            pos_bytes = struct.pack("<f", pos_clamped)  # little-endian float
            vel_bytes = struct.pack("<f", vel_clamped)

            # 数据格式: p_des (4 bytes) + v_des (4 bytes)
            cmd_data = pos_bytes + vel_bytes

            # CAN ID = 0x100 + motor_id
            send_id = motor_id[0]
            arb_id = 0x100 + send_id

            self.send_can_frame(motor_id, cmd_data, motor_can_id=arb_id)
            self._goal_position_cache[motor_id] = pos_clamped
            logger.debug(f"Sent position-velocity control to {motor_id}: pos={position:.3f}, vel={velocity:.3f}")

        except OperationalError:
            raise
        except Exception as e:
            logger.error(f"Failed to send position-velocity control to {motor_id}: {e}")
            raise OperationalError(
                i18n_key="hardware.motor_device.send_failed", retriable=True, motor_id=motor_id
            ) from e

    def send_velocity_control(
        self,
        motor_id: tuple[int, int],
        velocity: float,
    ) -> None:
        """Send velocity control command (0x200+ID mode).

        控制报文 ID: 0x200+ID
        数据格式: v_des[D0-D3]

        Args:
            motor_id: Motor identifier (send_id, recv_id)
            velocity: Target velocity in rad/s (浮点型, 低位在前, 高位在后)

        Raises:
            OperationalError: On send failure
        """
        try:
            # 获取电机限制
            _, vmax, _ = self.register.get_pmax_vmax_tmax(motor_id)

            # 限制范围
            vel_clamped = max(-vmax, min(vmax, velocity))

            # 速度是浮点型, 低位在前, 高位在后
            import struct

            vel_bytes = struct.pack("<f", vel_clamped)

            # 数据格式: v_des (4 bytes), 其余补0
            cmd_data = vel_bytes + bytes([0, 0, 0, 0])

            # CAN ID = 0x200 + motor_id
            send_id = motor_id[0]
            arb_id = 0x200 + send_id

            self.send_can_frame(motor_id, cmd_data, motor_can_id=arb_id)
            self._goal_position_cache[motor_id] = None  # No position goal in velocity mode
            logger.debug(f"Sent velocity control to {motor_id}: vel={velocity:.3f}")

        except OperationalError:
            raise
        except Exception as e:
            logger.error(f"Failed to send velocity control to {motor_id}: {e}")
            raise OperationalError(
                i18n_key="hardware.motor_device.send_failed", retriable=True, motor_id=motor_id
            ) from e

    def send_torque_position_control(
        self,
        motor_id: tuple[int, int],
        position: float,
        velocity_limit: float,
        current_limit: float,
    ) -> None:
        """Send torque-position hybrid control command (0x300+ID mode).

        控制报文 ID: 0x300+ID
        数据格式: p_des[D0-D3], v_des[D4-D5], i_des[D6-D7]

        Args:
            motor_id: Motor identifier (send_id, recv_id)
            position: Target position in rad (单位为rad, 浮点类型4字节, 低位在前, 高位在后)
            velocity_limit: Velocity limit in rad/s (限速值, 单位rad/s, 放大100倍, 类型为无符号16位)
                           范围: 0-10000, 超过10000会限制在10000, 对应的实际速度限速幅值为0~100rad/s
            current_limit: Current limit (扭矩电流限定标幺值, 放大10000倍, 类型为无符号16位)
                          范围: 0-10000, 超过10000会限制在10000
                          对应的原始电流限定标幺值为0~1.0, 实际电流除以最大相电流

        Raises:
            OperationalError: On send failure
        """
        try:
            # 获取电机限制
            pmax, _, _ = self.register.get_pmax_vmax_tmax(motor_id)

            # 位置限制
            pos_clamped = max(-pmax, min(pmax, position))

            # 速度限速值: 放大100倍, 类型为无符号16位, 范围0-10000 (对应0-100rad/s)
            vel_limit_scaled = int(max(0, min(10000, velocity_limit * 100)))

            # 电流限定: 放大10000倍, 类型为无符号16位, 范围0-10000 (对应0-1.0标幺值)
            current_limit_scaled = int(max(0, min(10000, current_limit * 10000)))

            # 数据格式:
            # D[0-3]: p_des (4字节浮点, 低位在前)
            # D[4-5]: v_des (2字节无符号16位, 放大100倍, 低位在前)
            # D[6-7]: i_des (2字节无符号16位, 放大10000倍, 低位在前)

            import struct

            pos_bytes = struct.pack("<f", pos_clamped)  # 4字节浮点, little-endian

            cmd_data = pos_bytes + bytes(
                [
                    vel_limit_scaled & 0xFF,  # D[4]: v_des低位
                    (vel_limit_scaled >> 8) & 0xFF,  # D[5]: v_des高位
                    current_limit_scaled & 0xFF,  # D[6]: i_des低位
                    (current_limit_scaled >> 8) & 0xFF,  # D[7]: i_des高位
                ]
            )

            # CAN ID = 0x300 + motor_id
            send_id = motor_id[0]
            arb_id = 0x300 + send_id

            self.send_can_frame(motor_id, cmd_data, motor_can_id=arb_id)
            self._goal_position_cache[motor_id] = pos_clamped
            logger.debug(
                f"Sent torque-position control to {motor_id}: "
                f"pos={position:.3f}, vel_lim={velocity_limit:.2f}, i_lim={current_limit:.4f}"
            )

        except OperationalError:
            raise
        except Exception as e:
            logger.error(f"Failed to send torque-position control to {motor_id}: {e}")
            raise OperationalError(
                i18n_key="hardware.motor_device.send_failed", retriable=True, motor_id=motor_id
            ) from e

    def send_motor_control(
        self,
        motor_id: tuple[int, int],
        enable: bool,
    ) -> None:
        """Send motor enable or disable command.

        使能/失能命令属于控制帧, 帧ID如前所述, 数据段定义如下:
        使能: D[0-6]=0xFF, D[7]=0xFC
        失能: D[0-6]=0xFF, D[7]=0xFD

        Args:
            motor_id: Motor identifier (send_id, recv_id)
            enable: True to enable motor, False to disable

        Raises:
            OperationalError: On send failure
        """
        try:
            # 数据格式: 0xFF * 7 + (0xFC for enable, 0xFD for disable)
            cmd_byte = 0xFC if enable else 0xFD
            cmd_data = bytes([0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, cmd_byte])

            # 发送到 send_id
            send_id = motor_id[0]

            self.send_can_frame(motor_id, cmd_data, motor_can_id=send_id)
            if not enable:
                self._goal_position_cache[motor_id] = None  # Clear goal on disable
            logger.debug(f"Sent {'enable' if enable else 'disable'} command to {motor_id}")

        except OperationalError:
            raise
        except Exception as e:
            logger.error(f"Failed to send motor control to {motor_id}: {e}")
            raise OperationalError(
                i18n_key="hardware.motor_device.send_failed", retriable=True, motor_id=motor_id
            ) from e

    def send_save_zero_position(
        self,
        motor_id: tuple[int, int],
    ) -> None:
        """Send command to save current position as zero point.

        保存位置零点命令属于控制帧:
        D[0-6]=0xFF, D[7]=0xFE

        该命令会将当前输出轴的位置设定成零点, 并将位置给定值设定成0.

        Args:
            motor_id: Motor identifier (send_id, recv_id)

        Raises:
            OperationalError: On send failure
        """
        try:
            # 数据格式: 0xFF * 7 + 0xFE
            cmd_data = bytes([0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFE])

            # 发送到 send_id
            send_id = motor_id[0]

            self.send_can_frame(motor_id, cmd_data, motor_can_id=send_id)
            logger.info(f"Sent save zero position command to {motor_id}")

        except OperationalError:
            raise
        except Exception as e:
            logger.error(f"Failed to send save zero position to {motor_id}: {e}")
            raise OperationalError(
                i18n_key="hardware.motor_device.send_failed", retriable=True, motor_id=motor_id
            ) from e

    def send_clear_error(
        self,
        motor_id: tuple[int, int],
    ) -> None:
        """Send command to clear motor errors.

        清除错误命令属于控制帧:
        D[0-6]=0xFF, D[7]=0xFB

        电机出现过热等错误时, 发送"清除"命令可以清除错误.

        Args:
            motor_id: Motor identifier (send_id, recv_id)

        Raises:
            OperationalError: On send failure
        """
        try:
            # 数据格式: 0xFF * 7 + 0xFB
            cmd_data = bytes([0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFB])

            # 发送到 send_id
            send_id = motor_id[0]

            self.send_can_frame(motor_id, cmd_data, motor_can_id=send_id)
            logger.info(f"Sent clear error command to {motor_id}")

        except OperationalError:
            raise
        except Exception as e:
            logger.error(f"Failed to send clear error to {motor_id}: {e}")
            raise OperationalError(
                i18n_key="hardware.motor_device.send_failed", retriable=True, motor_id=motor_id
            ) from e

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
            # NOTE: 0x01 is KT_VALUE per the DM-J4310 tables and should NOT be treated
            # as a model number. Some firmwares historically returned identifying
            # values at other addresses; use these as heuristics only (not from the
            # official spec). Prioritize 0x100 then 0x00 as fallbacks.
            # model_param_addrs = [0x100, 0x00]

            # Identification is not reliable across firmwares; return the generic fallback model.
            # We keep the legacy model_param_addrs variable for compatibility but no longer use it.
            logger.info(f"identify_model: returning generic Damiao model for motor {motor_id}")
            return DAMAIO_MODELS_LIST[0]

            # Fallback to provided model_number if available
            if model_number is not None:
                mi = select_model_for_number(model_number)
                if mi is None:
                    raise ValueError(f"Unknown Damiao model number: {model_number}")
                return mi

            # Could not determine model -> raise
            raise ValueError(
                f"Unable to identify Damiao motor model for {motor_id} (read failed or model mapping missing)"
            )

        except Exception as e:
            # Uniformly wrap any exception with operation-specific OperationalError
            if raise_on_ambiguous:
                logger.error(f"Error identifying motor {motor_id}: {e}")
                raise
            else:
                logger.warning(f"Identification failed for motor {motor_id}: {e}")
                raise OperationalError(
                    i18n_key="hardware.motor_device.identify_failed",
                    retriable=True,
                    motor_id=motor_id,
                ) from e

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

        self._recv_pause_event.clear()  # suspend receiving during scan
        time.sleep(0.05)  # brief delay to ensure receive thread is paused

        # Scan one motor at a time with delays to prevent bus errors
        # CAN buses accumulate errors when broadcasting to non-existent motors
        # This sequential approach is slower but more reliable for sparse motor deployments
        batch_size = 10  # Process one motor at a time
        for i in range(0, len(scan_range), batch_size):
            batch = scan_range[i : i + batch_size]

            # Filter out IDs that are known recv-only addresses
            send_ids_to_probe = [sid for sid in batch if sid not in discovered_recv_ids]
            if not send_ids_to_probe:
                continue

            # Process each motor ID individually
            for send_id in send_ids_to_probe:
                query_data = bytes(
                    [
                        send_id & 0xFF,
                        (send_id >> 8) & 0xFF,
                        DamiaoConstants.CAN_CMD_QUERY_PARAM,
                        DamiaoRegisters.MST_ID[0] & 0xFF,
                        (DamiaoRegisters.MST_ID[0] >> 8) & 0xFF,
                        0,
                        0,
                        0,
                    ]
                )
                try:
                    msg = can.Message(arbitration_id=DamiaoConstants.PARAM_ID, data=query_data, is_extended_id=False)
                    self.bus.send(msg)
                except Exception:
                    continue

            timeout = 0.02
            start_time = time.time()
            while (time.time() - start_time) < timeout:
                msg = self.bus.recv(timeout=0.005)
                if msg and msg.data:
                    # Check if response matches any send_id
                    resp_send_id = int(msg.data[0]) | (int(msg.data[1]) << 8)
                    if resp_send_id in send_ids_to_probe:
                        # Determine recv_id from response
                        recv_id = int.from_bytes(msg.data[4:8], byteorder="little", signed=False)
                        discovered_recv_ids.add(recv_id)

                        id_tuple = (resp_send_id, recv_id)

                        try:
                            # Identify motor model
                            model_info = self.identify_model(id_tuple, raise_on_ambiguous=False)

                            discovered[id_tuple] = model_info
                            logger.info(
                                "Found motor send=%s recv=%s (%s)", resp_send_id, recv_id, discovered[id_tuple].model
                            )

                        except Exception as e:
                            logger.warning(f"Failed to identify motor {resp_send_id}, skipping: {e}")
                            continue

            time.sleep(0.01)  # brief delay between batches

        self._recv_pause_event.set()  # resume receiving
        logger.info(f"Scan complete: found {len(discovered)} motors")
        return discovered

    def read_telemetry(self, motor_id: tuple[int, int], model_info: MotorModelInfo) -> MotorTelemetry:
        """Read real-time telemetry from a single motor (uses raw-state helper)."""

        try:
            state = self.read_feedback(motor_id)
            if state is None:
                position, _, temp_rotor = self.register.get_current_state(motor_id)
                state = (0, position, 0.0, 0.0, 0, temp_rotor)

            position = state[1]
            velocity = state[2]
            torque = state[3]
            temp_rotor = state[5]
            current = 0.0

            velocity = model_info.convert_to_standard_unit("velocity", velocity)
            torque = model_info.convert_to_standard_unit("torque", torque)
            temp_rotor = model_info.convert_to_standard_unit("temperature", temp_rotor)

            if torque > 0:
                kt = self.register.read_float32(motor_id, DamiaoRegisters.KT_VALUE[0])
                current = torque / kt if kt != 0 else 0.0

            return MotorTelemetry(
                motor_id=motor_id,
                position=position,
                position_type=PositionType.RAW,
                goal_position=self._goal_position_cache.get(motor_id),
                velocity=velocity,
                torque=torque,
                current=current,
                voltage=None,
                temperature=temp_rotor,
                moving=abs(velocity) > 0.01,
                error=0,
            )
        except OperationalError:
            raise
        except Exception as e:
            raise OperationalError(
                i18n_key="hardware.motor_device.read_failed",
                retriable=True,
                motor_id=motor_id,
            ) from e

    def bulk_read_telemetry(
        self, motors: dict[tuple[int, int], MotorModelInfo]
    ) -> dict[tuple[int, int], MotorTelemetry]:
        """Read telemetry from multiple motors efficiently using concurrent CAN frames.

        Uses `bulk_read_raw_states` to obtain raw frames and then decodes them.
        """
        if len(motors) == 0:
            return {}

        motors_no_state: list[tuple[int, int]] = []
        for mid in motors.keys():
            raw = self.cache.get_status_raw(mid, max_age=0.5)
            if raw is None:
                motors_no_state.append(mid)

        # load missing states in bulk
        if motors_no_state:
            self.register.bulk_get_current_state(motors_no_state)

        # load KT values in bulk
        self.bulk_read_parameters([(mid, DamiaoRegisters.KT_VALUE[0]) for mid in motors.keys()])

        return {mid: self.read_telemetry(mid, motor_info) for mid, motor_info in motors.items()}

    def _get_register_address(self, name: str) -> int:
        """Return register address for a logical name when available.

        Supported names (best-effort): "position" -> XOUT, "temperature" -> TMTR,
        "voltage" -> VBUS, "operation_mode" -> CTRL_MODE. Names that are not applicable (e.g., "goal_position",
        "torque_enable") will raise NotImplementedError.
        """
        mapping = {
            "position": DamiaoRegisters.XOUT[0],
            "temperature": DamiaoRegisters.TMTR[0],
            "voltage": DamiaoRegisters.VBUS[0],
            "operation_mode": DamiaoRegisters.CTRL_MODE[0],
        }
        try:
            return mapping[name]
        except KeyError as e:
            raise NotImplementedError(f"Named register '{name}' not supported by DamiaoCAN_Driver") from e

    def read_register(self, motor_id: tuple[int, int], address: int) -> float:
        return self.register.read_number(motor_id, address, max_age=2.0)

    def write_register(self, motor_id: tuple[int, int], address: int, value: float) -> None:
        self.register.write_number(motor_id, address, value)

    def bulk_read_registers(self, motor_ids: list[tuple[int, int]], register_addr: int) -> dict[tuple[int, int], float]:
        return { mid[0]: value for mid, value in self.register.bulk_read_numbers([(mid, register_addr) for mid in motor_ids], max_age=2.0).items() }

    def bulk_write_registers(self, motor_values: dict[tuple[int, int], float], register_addr: int) -> None:
        self.register.bulk_write_numbers([(mid, register_addr, value) for mid, value in motor_values.items()])

    def set_torque(self, motor_id: tuple[int, int], enabled: bool) -> None:
        """
        Enable or disable motor torque.

        **Deprecated**: This legacy enable/disable API is scheduled for removal.
        Prefer driver-specific torque control APIs (`write_torque` / `read_torque`) or
        use value-level APIs where supported.

        Args:
            motor_id: Motor ID
            enabled: True to enable torque, False to disable

        """
        self.send_motor_control(motor_id, enable=enabled)

    def bulk_set_torque(self, motor_ids: list[tuple[int, int]], enabled: bool) -> None:
        """
        Set torque for multiple motors at once (more efficient than individual calls).

        Args:
            motor_ids: List of motor IDs
            enabled: True to enable, False to disable

        """
        for mid in motor_ids:
            self.send_motor_control(mid, enable=enabled)

    def get_position(self, motor_id: tuple[int, int]) -> float:
        """Get current motor position in radians."""
        state = self.read_feedback(motor_id)
        if state is None:
            position = self.register.get_current_position(motor_id)
            return position
        else:
            return state[1]

    def bulk_get_position(self, motor_ids: list[tuple[int, int]]) -> dict[tuple[int, int], float]:
        results: dict[tuple[int, int], float] = {}
        motors_no_state: list[tuple[int, int]] = []
        for mid in motor_ids:
            state = self.read_feedback(mid)
            if state is None:
                motors_no_state.append(mid)
            else:
                results[mid] = state[1]
        for mid, position in self.register.bulk_get_current_position(motors_no_state).items():
            results[mid] = position
        return results

    def get_goal_position(self, motor_id: tuple[int, int]) -> float:
        goal = self._goal_position_cache[motor_id]
        if goal is not None:
            return goal

        return self.get_position(motor_id)  # use current position as fallback if we don't have a cached goal

    def set_goal_position(self, motor_id: tuple[int, int], position: float) -> None:
        op_mode = self.get_operation_mode(motor_id)
        if op_mode == 1:
            self.send_mit_control(motor_id, position, 0.0, 0.0)
        raise NotImplementedError("Setting goal position is only supported in MIT control mode (1)")

    def bulk_get_goal_position(self, motor_ids: list[tuple[int, int]]) -> dict[tuple[int, int], float]:
        result : dict[tuple[int, int], float] = {}
        missing_goal_ids: list[tuple[int, int]] = []
        for mid in motor_ids:
            goal = self._goal_position_cache[mid]
            if goal is not None:
                result[mid] = goal
            else:
                missing_goal_ids.append(mid)
        if missing_goal_ids:
            for mid in missing_goal_ids:
                result[mid] = self.get_position(mid)  # fallback to current position if no cached goal
        return result

    def bulk_set_goal_position(self, motor_positions: dict[tuple[int, int], float]) -> None:
        for mid, pos in motor_positions.items():
            self.set_goal_position(mid, pos)
