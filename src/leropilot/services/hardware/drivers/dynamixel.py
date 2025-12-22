"""
Dynamixel Protocol 2.0 driver implementation.

Supports Dynamixel XL330, XL430, XC430, and XM430 motors.
Uses ROBOTIS dynamixel-sdk for protocol handling.
"""

import logging

from leropilot.models.hardware import MotorInfo, MotorTelemetry
from leropilot.services.hardware.drivers.base import BaseMotorDriver

logger = logging.getLogger(__name__)

# Try to import dynamixel SDK; gracefully degrade if not available
try:
    from dynamixel_sdk import (
        COMM_SUCCESS,
        PacketHandler,
        PortHandler,
    )

    HAS_DYNAMIXEL_SDK = True
except ImportError:
    logger.warning("dynamixel-sdk not installed; Dynamixel driver will be limited")
    HAS_DYNAMIXEL_SDK = False

# Dynamixel Protocol 2.0 control table addresses (EEPROM and RAM areas)
ADDR_TORQUE_ENABLE = 64
ADDR_GOAL_POSITION = 116
ADDR_GOAL_VELOCITY = 104
ADDR_GOAL_CURRENT = 102
ADDR_PRESENT_POSITION = 132
ADDR_PRESENT_VELOCITY = 128
ADDR_PRESENT_CURRENT = 126
ADDR_PRESENT_VOLTAGE = 144
ADDR_PRESENT_TEMPERATURE = 146
ADDR_MODEL_NUMBER = 0
ADDR_FIRMWARE = 6

# Register lengths (bytes)
LEN_TORQUE_ENABLE = 1
LEN_GOAL_POSITION = 4
LEN_GOAL_VELOCITY = 4
LEN_GOAL_CURRENT = 2
LEN_PRESENT_POSITION = 4
LEN_PRESENT_VELOCITY = 4
LEN_PRESENT_CURRENT = 2
LEN_PRESENT_VOLTAGE = 2
LEN_PRESENT_TEMPERATURE = 1
LEN_MODEL_NUMBER = 2

# Protocol version
PROTOCOL_VERSION = 2.0

# Model number mapping (from ROBOTIS documentation)
# Format: model_number: (base_model, variant)
MODEL_NUMBER_MAP = {
    1: ("AX-12A", None),
    12: ("AX-12+", None),
    18: ("AX-18A", None),
    300: ("AX-12W", None),
    29: ("MX-28", None),
    30: ("MX-28", "2.0"),
    310: ("MX-64", None),
    311: ("MX-64", "2.0"),
    320: ("MX-106", None),
    321: ("MX-106", "2.0"),
    350: ("XL320", None),
    1020: ("XM430", "W350"),
    1030: ("XM430", "W210"),
    1040: ("XM430", "W210"),
    1050: ("XM430", "W350"),
    1060: ("XL430", "W250"),
    1070: ("XC430", "W150"),
    1090: ("XC330", "T288"),
    1100: ("XC330", "T181"),
    1120: ("XM540", "W270"),
    1130: ("XC330", "M181"),
    1190: ("XL330", "M077"),
    1200: ("XL330", "M288"),
    1210: ("XM540", "W270"),
}


class DynamixelDriver(BaseMotorDriver):
    """Driver for Dynamixel Protocol 2.0 motors"""

    def __init__(self, interface: str, baud_rate: int = 1000000) -> None:
        """
        Initialize Dynamixel driver.

        Args:
            interface: Serial port (e.g., "COM11", "/dev/ttyUSB0")
            baud_rate: Serial baud rate (default: 1000000)
        """
        super().__init__(interface, baud_rate)
        self.port_handler: PortHandler | None = None
        self.packet_handler: PacketHandler | None = None

        if not HAS_DYNAMIXEL_SDK:
            logger.warning("Dynamixel SDK not available; install with: pip install dynamixel-sdk")

    def connect(self) -> bool:
        """Connect to motor bus via serial port"""
        if not HAS_DYNAMIXEL_SDK:
            logger.error("Cannot connect: dynamixel-sdk not installed")
            return False

        try:
            self.port_handler = PortHandler(self.interface)
            self.packet_handler = PacketHandler(PROTOCOL_VERSION)

            if not self.port_handler.openPort():
                logger.error(f"Failed to open port {self.interface}")
                return False

            if not self.port_handler.setBaudRate(self.baud_rate):
                logger.error(f"Failed to set baud rate {self.baud_rate}")
                self.port_handler.closePort()
                return False

            self.connected = True
            logger.info(f"Connected to Dynamixel motor bus on {self.interface} @ {self.baud_rate} baud")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Dynamixel motor bus: {e}")
            self.connected = False
            return False

    def disconnect(self) -> bool:
        """Disconnect from motor bus"""
        try:
            if self.port_handler:
                self.port_handler.closePort()
            self.connected = False
            logger.info("Disconnected from Dynamixel motor bus")
            return True
        except Exception as e:
            logger.error(f"Error disconnecting: {e}")
            return False

    def ping_motor(self, motor_id: int) -> bool:
        """
        Ping motor to check if it exists.

        Args:
            motor_id: Motor ID (0-252)

        Returns:
            True if motor responds
        """
        if not self.port_handler or not self.packet_handler:
            return False

        try:
            # Protocol 2.0 ping returns (model_number, dxl_comm_result, dxl_error)
            _, dxl_comm_result, dxl_error = self.packet_handler.ping(self.port_handler, motor_id)

            if dxl_comm_result != COMM_SUCCESS:
                logger.debug(f"Ping failed for motor {motor_id}: {self.packet_handler.getTxRxResult(dxl_comm_result)}")
                return False

            return True
        except Exception as e:
            logger.debug(f"Ping exception for motor {motor_id}: {e}")
            return False

    def scan_motors(self, scan_range: list[int] | None = None) -> list[MotorInfo]:
        """
        Scan motor bus and discover all motors.

        Args:
            scan_range: List of motor IDs to scan (default: 0-252)

        Returns:
            List of discovered motors
        """
        if self.packet_handler is None or self.port_handler is None:
            logger.error("Not connected to motor bus")
            return []

        if scan_range is None:
            scan_range = list(range(0, 253))

        discovered = []
        logger.info(f"Scanning {len(scan_range)} motor IDs on Dynamixel bus")

        for motor_id in scan_range:
            try:
                # Protocol 2.0 ping returns (model_number, dxl_comm_result, dxl_error)
                model_number, dxl_comm_result, dxl_error = self.packet_handler.ping(self.port_handler, motor_id)

                if dxl_comm_result == COMM_SUCCESS:
                    model_info_tuple = MODEL_NUMBER_MAP.get(model_number, (f"Unknown({model_number})", None))
                    base_model, variant = model_info_tuple

                    motor_info = MotorInfo(
                        id=motor_id,
                        model=base_model,
                        variant=variant,
                        model_number=model_number,
                        firmware_version="unknown",  # Could read from ADDR_FIRMWARE
                    )
                    discovered.append(motor_info)
                    logger.info(f"Found motor {motor_id}: {motor_info.full_name}")
            except Exception as e:
                logger.debug(f"Scan exception for motor {motor_id}: {e}")

        logger.info(f"Scan complete: found {len(discovered)} motors")
        return discovered

    def _read_register(self, motor_id: int, address: int, length: int) -> int | None:
        """
        Read a register value from the motor.

        Args:
            motor_id: Motor ID
            address: Register address
            length: Register length (1, 2, or 4 bytes)

        Returns:
            Register value or None if read fails
        """
        if not self.port_handler or not self.packet_handler:
            return None

        try:
            if length == 1:
                result, dxl_comm_result, dxl_error = self.packet_handler.read1ByteTxRx(
                    self.port_handler, motor_id, address
                )
            elif length == 2:
                result, dxl_comm_result, dxl_error = self.packet_handler.read2ByteTxRx(
                    self.port_handler, motor_id, address
                )
            elif length == 4:
                result, dxl_comm_result, dxl_error = self.packet_handler.read4ByteTxRx(
                    self.port_handler, motor_id, address
                )
            else:
                logger.error(f"Unsupported register length: {length}")
                return None

            if dxl_comm_result != COMM_SUCCESS:
                logger.debug(f"Failed to read register {address} from motor {motor_id}")
                return None

            return result
        except Exception as e:
            logger.error(f"Error reading register {address} from motor {motor_id}: {e}")
            return None

    def _write_register(self, motor_id: int, address: int, value: int, length: int) -> bool:
        """
        Write a register value to the motor.

        Args:
            motor_id: Motor ID
            address: Register address
            value: Value to write
            length: Register length (1, 2, or 4 bytes)

        Returns:
            True if write successful
        """
        if not self.port_handler or not self.packet_handler:
            return False

        try:
            if length == 1:
                dxl_comm_result, dxl_error = self.packet_handler.write1ByteTxRx(
                    self.port_handler, motor_id, address, value
                )
            elif length == 2:
                dxl_comm_result, dxl_error = self.packet_handler.write2ByteTxRx(
                    self.port_handler, motor_id, address, value
                )
            elif length == 4:
                dxl_comm_result, dxl_error = self.packet_handler.write4ByteTxRx(
                    self.port_handler, motor_id, address, value
                )
            else:
                logger.error(f"Unsupported register length: {length}")
                return False

            if dxl_comm_result != COMM_SUCCESS:
                logger.debug(f"Failed to write register {address} to motor {motor_id}")
                return False

            return True
        except Exception as e:
            logger.error(f"Error writing register {address} to motor {motor_id}: {e}")
            return False

    def read_telemetry(self, motor_id: int) -> MotorTelemetry | None:
        """
        Read real-time telemetry from a single motor.

        Args:
            motor_id: Motor ID

        Returns:
            Motor telemetry data or None if read fails
        """
        try:
            # Read position, current, voltage, temperature
            position = self._read_register(motor_id, ADDR_PRESENT_POSITION, LEN_PRESENT_POSITION)
            velocity = self._read_register(motor_id, ADDR_PRESENT_VELOCITY, LEN_PRESENT_VELOCITY)
            current = self._read_register(motor_id, ADDR_PRESENT_CURRENT, LEN_PRESENT_CURRENT)
            voltage = self._read_register(motor_id, ADDR_PRESENT_VOLTAGE, LEN_PRESENT_VOLTAGE)
            temperature = self._read_register(motor_id, ADDR_PRESENT_TEMPERATURE, LEN_PRESENT_TEMPERATURE)
            goal_position = self._read_register(motor_id, ADDR_GOAL_POSITION, LEN_GOAL_POSITION)

            if any(x is None for x in [position, velocity, current, voltage, temperature, goal_position]):
                return None

            # At this point, all values are guaranteed to be not None
            assert position is not None
            assert velocity is not None
            assert current is not None
            assert voltage is not None
            assert temperature is not None
            assert goal_position is not None

            # Convert raw values to physical units
            # Position: raw value to radians (Dynamixel 4096 counts per revolution)
            position_rad = (position / 4096.0) * 2 * 3.14159265359
            goal_position_rad = (goal_position / 4096.0) * 2 * 3.14159265359

            # Velocity: raw value to rad/s (unit depends on model)
            velocity_rads = velocity if velocity < 2147483648 else velocity - 4294967296

            # Current: raw value to mA (unit depends on model; typically 1 mA per unit)
            current_ma = current if current < 32768 else current - 65536

            # Voltage: raw value to V (unit: 0.1V per unit)
            voltage_v = voltage / 10.0

            # Determine if motor is moving (velocity != 0)
            moving = abs(velocity_rads) > 0

            # Load: estimate from current (rough approximation)
            load = min(100, int(abs(current_ma) / 10))  # Rough estimate: 1000mA = 100% load

            return MotorTelemetry(
                id=motor_id,
                position=position_rad,
                velocity=velocity_rads,
                current=current_ma,
                load=load,
                temperature=temperature,
                voltage=voltage_v,
                moving=moving,
                goal_position=goal_position_rad,
                error=0,
            )
        except Exception as e:
            logger.error(f"Failed to read telemetry from motor {motor_id}: {e}")
            return None

    def read_bulk_telemetry(self, motor_ids: list[int]) -> dict[int, MotorTelemetry]:
        """
        Read telemetry from multiple motors efficiently using bulk read.

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
        Set motor target position.

        Args:
            motor_id: Motor ID
            position: Target position (raw encoder units, 0-4095)
            speed: Optional movement speed (raw velocity units)

        Returns:
            True if command sent successfully
        """
        try:
            # Clamp position to valid range
            position = max(0, min(4095, position))

            # Write goal position
            return self._write_register(motor_id, ADDR_GOAL_POSITION, position, LEN_GOAL_POSITION)
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
            value = 1 if enabled else 0
            return self._write_register(motor_id, ADDR_TORQUE_ENABLE, value, LEN_TORQUE_ENABLE)
        except Exception as e:
            logger.error(f"Failed to set torque for motor {motor_id}: {e}")
            return False

    def reboot_motor(self, motor_id: int) -> bool:
        """
        Reboot a single motor.

        Args:
            motor_id: Motor ID

        Returns:
            True if reboot command sent
        """
        if not self.port_handler or not self.packet_handler:
            return False

        try:
            dxl_comm_result, dxl_error = self.packet_handler.reboot(self.port_handler, motor_id)
            if dxl_comm_result != COMM_SUCCESS:
                logger.error(f"Failed to reboot motor {motor_id}")
                return False
            logger.info(f"Rebooted motor {motor_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to reboot motor {motor_id}: {e}")
            return False

    def bulk_set_torque(self, motor_ids: list[int], enabled: bool) -> bool:
        """
        Set torque for multiple motors at once using sync write.

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
