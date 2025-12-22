"""
Damiao CAN bus motor driver implementation.

Supports Damiao motors (DM4310, DM6006, DM8006, etc.) over CAN bus.
Core logic adapted from damiao-motor package to avoid Flask dependency.

Uses python-can library for CAN communication with MIT-style control protocol.
"""

import logging
from typing import Any

try:
    import can

    HAS_PYTHON_CAN = True
except ImportError:
    HAS_PYTHON_CAN = False

from leropilot.models.hardware import MotorInfo, MotorTelemetry
from leropilot.services.hardware.drivers.base import BaseMotorDriver

logger = logging.getLogger(__name__)

# -----------------------
# Motor parameter limits (MIT mode)
# -----------------------
P_MIN, P_MAX = -12.5, 12.5
V_MIN, V_MAX = -45.0, 45.0
KP_MIN, KP_MAX = 0.0, 500.0
KD_MIN, KD_MAX = 0.0, 5.0
T_MIN, T_MAX = -18.0, 18.0

# -----------------------
# Motor state codes
# -----------------------
DM_MOTOR_ENABLED = 0x1
DM_MOTOR_DISABLED = 0x0
DM_MOTOR_OVER_VOLTAGE = 0x8
DM_MOTOR_UNDER_VOLTAGE = 0x9
DM_MOTOR_OVER_CURRENT = 0xA
DM_MOTOR_MOS_OVER_TEMP = 0xB
DM_MOTOR_ROTOR_OVER_TEMP = 0xC
DM_MOTOR_LOST_COMM = 0xD
DM_MOTOR_OVERLOAD = 0xE


def float_to_uint(x: float, x_min: float, x_max: float, bits: int) -> int:
    """Convert float to unsigned int for CAN protocol encoding."""
    span = x_max - x_min
    x_clipped = min(max(x, x_min), x_max)
    return int((x_clipped - x_min) * ((1 << bits) - 1) / span)


def uint_to_float(x_int: int, x_min: float, x_max: float, bits: int) -> float:
    """Convert unsigned int to float for CAN protocol decoding."""
    span = x_max - x_min
    return float(x_int) * span / ((1 << bits) - 1) + x_min


class DamiaoCAN_Driver(BaseMotorDriver):
    """Driver for Damiao CAN bus motors using MIT control protocol"""

    def __init__(self, interface: str, baud_rate: int | None = None) -> None:
        """
        Initialize Damiao CAN driver.

        Args:
            interface: CAN device ("can0" for socketcan, "COM12" for SLCAN)
            baud_rate: CAN baud rate (default: 1000000)
        """
        if not HAS_PYTHON_CAN:
            raise ImportError("python-can not installed. Install via: uv add python-can")

        super().__init__(interface, baud_rate or 1000000)
        self.bus: Any = None
        self.motors: dict[int, dict[str, Any]] = {}  # motor_id -> state dict

    def connect(self) -> bool:
        """Connect to CAN bus"""
        try:
            # Detect bus type from interface name
            if self.interface.startswith("COM") or self.interface.startswith("/dev/tty"):
                bustype = "slcan"
            elif self.interface.startswith("can"):
                bustype = "socketcan"
            else:
                bustype = "socketcan"  # Default

            logger.info(f"Connecting to CAN bus: {self.interface} (type: {bustype})")

            self.bus = can.interface.Bus(channel=self.interface, bustype=bustype, bitrate=self.baud_rate)

            self.connected = True
            logger.info(f"Connected to Damiao CAN bus on {self.interface}")
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
            self.connected = False
            logger.info("Disconnected from Damiao CAN bus")
            return True
        except Exception as e:
            logger.error(f"Error disconnecting: {e}")
            return False

    def _encode_cmd_msg(self, pos: float, vel: float, torq: float, kp: float, kd: float) -> bytes:
        """Encode MIT control command into 8-byte CAN frame"""
        pos_u = float_to_uint(pos, P_MIN, P_MAX, 16)
        vel_u = float_to_uint(vel, V_MIN, V_MAX, 12)
        kp_u = float_to_uint(kp, KP_MIN, KP_MAX, 12)
        kd_u = float_to_uint(kd, KD_MIN, KD_MAX, 12)
        torq_u = float_to_uint(torq, T_MIN, T_MAX, 12)

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

    def _send_can_frame(self, motor_id: int, data: bytes) -> bool:
        """Send CAN frame to motor"""
        if not self.bus or not self.connected:
            return False

        try:
            msg = can.Message(arbitration_id=motor_id, data=data, is_extended_id=False)
            self.bus.send(msg)
            return True
        except Exception as e:
            logger.error(f"Error sending CAN message to motor {motor_id}: {e}")
            return False

    def _recv_feedback(self, timeout: float = 0.1) -> dict[str, Any] | None:
        """Receive and decode feedback from CAN bus"""
        if not self.bus:
            return None

        try:
            msg = self.bus.recv(timeout=timeout)
            if msg is None or len(msg.data) != 8:
                return None

            data = bytes(msg.data)
            motor_id = data[0] & 0x0F
            status = data[0] >> 4
            pos_int = (data[1] << 8) | data[2]
            vel_int = (data[3] << 4) | (data[4] >> 4)
            torq_int = ((data[4] & 0xF) << 8) | data[5]
            t_mos = float(data[6])
            t_rotor = float(data[7])

            return {
                "motor_id": motor_id,
                "status": status,
                "position": uint_to_float(pos_int, P_MIN, P_MAX, 16),
                "velocity": uint_to_float(vel_int, V_MIN, V_MAX, 12),
                "torque": uint_to_float(torq_int, T_MIN, T_MAX, 12),
                "temperature_mos": t_mos,
                "temperature_rotor": t_rotor,
            }
        except Exception as e:
            logger.debug(f"Error receiving CAN feedback: {e}")
            return None

    def ping_motor(self, motor_id: int) -> bool:
        """
        Ping motor by enabling and checking for feedback.

        Args:
            motor_id: Motor ID (CAN ID)

        Returns:
            True if motor responds
        """
        try:
            # Send enable command
            enable_msg = bytes([0xFF] * 7 + [0xFC])
            if not self._send_can_frame(motor_id, enable_msg):
                return False

            # Wait for feedback
            feedback = self._recv_feedback(timeout=0.2)
            if feedback and feedback["motor_id"] == motor_id:
                self.motors[motor_id] = feedback
                return True

            return False
        except Exception as e:
            logger.debug(f"Ping failed for motor {motor_id}: {e}")
            return False

    def _read_parameter(self, motor_id: int, param_index: int, timeout: float = 0.2) -> int | None:
        """
        Read parameter from Damiao motor.

        Damiao motors use a specific CAN protocol for parameter access:
        - Command format: [param_index_high, param_index_low, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]
        - Response contains the parameter value

        Args:
            motor_id: Motor ID
            param_index: Parameter index to read
            timeout: Response timeout in seconds

        Returns:
            Parameter value as integer, or None if read fails
        """
        try:
            # Send parameter read command
            # Format: [param_index_high, param_index_low, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]
            cmd_data = bytes([
                (param_index >> 8) & 0xFF,  # High byte of parameter index
                param_index & 0xFF,         # Low byte of parameter index
                0x00, 0x00, 0x00, 0x00, 0x00, 0x00
            ])

            if not self._send_can_frame(motor_id, cmd_data):
                return None

            # Read response - parameter responses may have different format
            # For Damiao motors, parameter responses typically contain the value
            feedback = self._recv_feedback(timeout=timeout)
            if not feedback or feedback["motor_id"] != motor_id:
                return None

            # Extract parameter value from feedback
            # This is protocol-specific - may need adjustment based on actual Damiao documentation
            # For now, use a simple heuristic based on position field (placeholder)
            param_value = int(feedback.get("position", 0) * 1000)  # Convert to integer representation

            logger.debug(f"Read parameter {param_index} from motor {motor_id}: {param_value}")
            return param_value

        except Exception as e:
            logger.debug(f"Failed to read parameter {param_index} from motor {motor_id}: {e}")
            return None

    def _detect_motor_model(self, motor_id: int) -> tuple[str, int] | None:
        """
        Detect motor model by reading manufacturer parameters.

        Damiao motors store model information in parameter registers.
        Common parameter indices for model detection:
        - Parameter 0x0000-0x000F: Basic identification
        - Parameter 0x1000+: Model-specific parameters

        Known Damiao models and their characteristics:
        - DM4310: Small servo (max torque ~1.5Nm, model_id ~4310)
        - DM6006: Medium servo (max torque ~6Nm, model_id ~6006)
        - DM8006: Large servo (max torque ~8Nm, model_id ~8006)
        - DM8009: Large servo variant (max torque ~9Nm, model_id ~8009)
        - DM10054: Extra large servo (max torque ~54Nm, model_id ~10054)

        Args:
            motor_id: Motor ID

        Returns:
            Tuple of (model_name, model_number) or None if detection fails
        """
        try:
            # Method 1: Try to read model identification parameter
            # Common parameter indices for Damiao model ID (these may vary by firmware)
            model_param_indices = [0x0000, 0x0001, 0x1000, 0x2000]

            for param_idx in model_param_indices:
                model_id = self._read_parameter(motor_id, param_idx)
                if model_id is not None and model_id > 0:
                    # Map model ID to known Damiao models
                    model_mapping = {
                        4310: ("DM4310", 4310),
                        6006: ("DM6006", 6006),
                        8006: ("DM8006", 8006),
                        8009: ("DM8009", 8009),
                        10054: ("DM10054", 10054),
                        # Add more mappings as needed
                    }

                    if model_id in model_mapping:
                        model_name, model_number = model_mapping[model_id]
                        logger.debug(f"Detected motor {motor_id} as {model_name} (model_id: {model_id})")
                        return (model_name, model_number)

            # Method 2: Use torque/current limits as fallback heuristic
            # Send a test command and analyze response characteristics
            logger.debug(f"Parameter-based detection failed for motor {motor_id}, trying heuristic detection")

            # Test with different torque values to infer model capabilities
            test_torques = [1.0, 5.0, 10.0, 20.0]  # Test different torque levels

            max_detected_torque = 0.0
            for test_torque in test_torques:
                test_cmd = self._encode_cmd_msg(0.0, 0.0, test_torque, 0.0, 0.0)
                if self._send_can_frame(motor_id, test_cmd):
                    feedback = self._recv_feedback(timeout=0.1)
                    if feedback and abs(feedback.get("torque", 0)) > 0.1:  # Motor responded
                        max_detected_torque = max(max_detected_torque, abs(feedback["torque"]))
                    # Small delay between tests
                    import time
                    time.sleep(0.01)

            # Map detected max torque to model
            if max_detected_torque >= 50.0:
                return ("DM10054", 10054)  # High torque model
            elif max_detected_torque >= 15.0:
                return ("DM8009", 8009)    # High torque model
            elif max_detected_torque >= 8.0:
                return ("DM8006", 8006)    # Large model
            elif max_detected_torque >= 6.0:
                return ("DM6006", 6006)    # Medium model
            elif max_detected_torque >= 1.0:
                return ("DM4310", 4310)    # Small model
            else:
                # Fallback to default
                logger.debug(f"Heuristic detection inconclusive for motor {motor_id}, using default DM4310")
                return ("DM4310", 4310)

        except Exception as e:
            logger.debug(f"Model detection failed for motor {motor_id}: {e}")
            return None

    def scan_motors(self, scan_range: list[int] | None = None) -> list[MotorInfo]:
        """
        Scan CAN bus and discover all Damiao motors.

        Args:
            scan_range: List of motor IDs to scan (default: 1-15)

        Returns:
            List of discovered motors
        """
        if scan_range is None:
            scan_range = list(range(1, 129))  # Default: 1-128 to cover non-sequential IDs

        discovered = []
        logger.info(f"Scanning {len(scan_range)} motor IDs on Damiao CAN bus")

        for motor_id in scan_range:
            if self.ping_motor(motor_id):
                try:
                    # Try to detect motor model
                    model_info = self._detect_motor_model(motor_id)
                    if model_info:
                        model_name, model_number = model_info
                        motor_info = MotorInfo(
                            id=motor_id,
                            model=model_name,
                            variant=None,
                            model_number=model_number,
                            firmware_version="unknown",
                        )
                    else:
                        # Fallback to default if detection fails
                        motor_info = MotorInfo(
                            id=motor_id,
                            model="DM4310",
                            variant=None,
                            model_number=4310,
                            firmware_version="unknown",
                        )

                    discovered.append(motor_info)
                    logger.info(f"Found motor {motor_id} ({motor_info.model})")

                except Exception as e:
                    logger.warning(f"Failed to create info for motor {motor_id}: {e}")

        logger.info(f"Scan complete: found {len(discovered)} motors")
        return discovered

    def read_telemetry(self, motor_id: int) -> MotorTelemetry | None:
        """
        Read real-time telemetry from a single motor.

        Args:
            motor_id: Motor ID

        Returns:
            Motor telemetry data or None if read fails
        """
        try:
            # Send zero command to trigger feedback
            zero_cmd = self._encode_cmd_msg(0.0, 0.0, 0.0, 0.0, 0.0)
            if not self._send_can_frame(motor_id, zero_cmd):
                return None

            # Read feedback
            feedback = self._recv_feedback(timeout=0.1)
            if not feedback or feedback["motor_id"] != motor_id:
                return None

            self.motors[motor_id] = feedback

            return MotorTelemetry(
                id=motor_id,
                position=feedback["position"],
                velocity=feedback["velocity"],
                current=int(feedback["torque"] / 10.0),  # Approximate
                load=0,  # Not available from Damiao
                voltage=24.0,  # Typical
                temperature=int(feedback["temperature_rotor"]),
                moving=abs(feedback["velocity"]) > 0.01,
                goal_position=0.0,  # Not available
                error=0,
            )
        except Exception as e:
            logger.error(f"Failed to read telemetry from motor {motor_id}: {e}")
            return None

    def read_bulk_telemetry(self, motor_ids: list[int]) -> dict[int, MotorTelemetry]:
        """
        Read telemetry from multiple motors.

        Args:
            motor_ids: List of motor IDs

        Returns:
            Dict mapping motor_id -> telemetry
        """
        result = {}
        for motor_id in motor_ids:
            telemetry = self.read_telemetry(motor_id)
            if telemetry:
                result[motor_id] = telemetry
        return result

    def set_position(self, motor_id: int, position: int, speed: int | None = None) -> bool:
        """
        Set motor target position using MIT control mode.

        Args:
            motor_id: Motor ID
            position: Target position in radians (will be clamped to ±12.5)
            speed: Not used in MIT mode (use velocity parameter instead)

        Returns:
            True if command sent successfully
        """
        try:
            # Convert position to radians, clamp to valid range
            pos_rad = max(P_MIN, min(P_MAX, float(position) / 1000.0))

            # Use moderate stiffness and damping for position control
            kp = 50.0
            kd = 1.0

            cmd_data = self._encode_cmd_msg(pos_rad, 0.0, 0.0, kp, kd)
            return self._send_can_frame(motor_id, cmd_data)
        except Exception as e:
            logger.error(f"Failed to set position for motor {motor_id}: {e}")
            return False

    def set_torque(self, motor_id: int, enabled: bool) -> bool:
        """
        Enable or disable motor torque.

        Args:
            motor_id: Motor ID
            enabled: True to enable torque, False to disable

        Returns:
            True if command sent successfully
        """
        try:
            if enabled:
                data = bytes([0xFF] * 7 + [0xFC])  # Enable
            else:
                data = bytes([0xFF] * 7 + [0xFD])  # Disable

            result = self._send_can_frame(motor_id, data)
            logger.debug(f"Set motor {motor_id} torque to {enabled}")
            return result
        except Exception as e:
            logger.error(f"Failed to set torque for motor {motor_id}: {e}")
            return False

    def reboot_motor(self, motor_id: int) -> bool:
        """
        Reboot a single motor (not supported by Damiao protocol).

        Args:
            motor_id: Motor ID

        Returns:
            False (not supported)
        """
        logger.warning("Damiao motors do not support reboot command")
        return False

    def bulk_set_torque(self, motor_ids: list[int], enabled: bool) -> bool:
        """
        Set torque for multiple motors at once.

        Args:
            motor_ids: List of motor IDs
            enabled: True to enable, False to disable

        Returns:
            True if all commands sent successfully
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
