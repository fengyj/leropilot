"""
Dynamixel Protocol 2.0 driver implementation.

Supports Dynamixel XL330, XL430, XC430, and XM430 motors.
Uses ROBOTIS dynamixel-sdk for protocol handling.
"""

import logging

from dynamixel_sdk import (
    COMM_SUCCESS,
    GroupBulkRead,
    GroupBulkWrite,
    GroupSyncRead,
    GroupSyncWrite,
    PacketHandler,
    PortHandler,
)

from leropilot.models.hardware import MotorModelInfo, MotorTelemetry

from ..base import BaseMotorDriver
from .tables import DynamixelRegisters

logger = logging.getLogger(__name__)

# Protocol version
PROTOCOL_VERSION = 2.0

# Protocol version
PROTOCOL_VERSION = 2.0

# Model number mapping (from ROBOTIS documentation)
# Format: model_number: (base_model, variant)
# Model number mapping moved to `dynamixel_tables.py` as typed `MotorModelInfo` entries.
# Keep the old mapping removed in favor of table-driven lookups.


class DynamixelDriver(BaseMotorDriver[int]):
    """Driver for Dynamixel Protocol 2.0 motors"""

    def __init__(self, interface: str, baud_rate: int | None = None) -> None:
        """
        Initialize Dynamixel driver.

        Args:
            interface: Serial port (e.g., "COM11", "/dev/ttyUSB0")
            baud_rate: Serial baud rate (default: 1000000)
        """
        super().__init__(interface, baud_rate)
        self.port_handler: PortHandler | None = None
        self.packet_handler: PacketHandler | None = None
        self.group_sync_read: GroupSyncRead | None = None
        self.group_sync_write: GroupSyncWrite | None = None
        self.group_bulk_read: GroupBulkRead | None = None
        self.group_bulk_write: GroupBulkWrite | None = None

    def connect(self) -> bool:
        """Connect to motor bus via serial port"""
        try:
            self.port_handler = PortHandler(self.interface)
            self.packet_handler = PacketHandler(PROTOCOL_VERSION)

            if not self.port_handler.openPort():
                logger.error(f"Failed to open port {self.interface}")
                return False

            # Use a default baud rate if none provided
            baud_to_set = int(self.baud_rate or 1000000)
            if not self.port_handler.setBaudRate(baud_to_set):
                logger.error(f"Failed to set baud rate {baud_to_set}")
                self.port_handler.closePort()
                return False

            # Initialize group handlers for bulk operations
            self.group_sync_read = GroupSyncRead(self.port_handler, self.packet_handler, 0, 0)
            self.group_sync_write = GroupSyncWrite(self.port_handler, self.packet_handler, 0, 0)
            self.group_bulk_read = GroupBulkRead(self.port_handler, self.packet_handler)
            self.group_bulk_write = GroupBulkWrite(self.port_handler, self.packet_handler)

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

    def scan_motors(self, scan_range: list[int] | None = None) -> dict[int, MotorModelInfo]:
        """
        Scan motor bus and discover all motors.

        Args:
            scan_range: List of motor IDs to scan (default: 0-252)

        Returns:
            Mapping of motor id -> MotorModelInfo for discovered motors
        """
        if self.packet_handler is None or self.port_handler is None:
            logger.error("Not connected to motor bus")
            return {}

        if scan_range is None:
            scan_range = list(range(0, 253))

        discovered: dict[int, MotorModelInfo] = {}
        logger.info(f"Scanning {len(scan_range)} motor IDs on Dynamixel bus")

        for motor_id in scan_range:
            try:
                # Protocol 2.0 ping returns (model_number, dxl_comm_result, dxl_error)
                model_number, dxl_comm_result, dxl_error = self.packet_handler.ping(self.port_handler, motor_id)

                if dxl_comm_result == COMM_SUCCESS:
                    from .tables import select_model_for_number

                    model_info = select_model_for_number(model_number)
                    if model_info:
                        discovered[motor_id] = model_info
                        logger.info(f"Found motor {motor_id}: {model_info.model}")
                    else:
                        logger.warning(f"Motor {motor_id} responded but model {model_number} not recognized")
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

            if dxl_comm_result != COMM_SUCCESS:
                logger.debug(f"Read failed for motor {motor_id}: {self.packet_handler.getTxRxResult(dxl_comm_result)}")
                raise RuntimeError("Failed to obtain model number via ping")
        except Exception as e:
            logger.debug(f"Read exception for motor {motor_id}: {e}")
            return None
        # If no return occurred above, signal read failure
        return None

    def identify_model(
        self,
        motor_id: int,
        model_number: int | None = None,
        fw_major: int | None = None,
        fw_minor: int | None = None,
        raise_on_ambiguous: bool = False,
    ) -> MotorModelInfo:
        """Identify a motor model using the model number register.

        The optional parameters are accepted for API compatibility; Dynamixel
        currently ignores pre-read values and reads model number via ping.

        Raises:
            RuntimeError: if the driver is not ready.
            ValueError: if the model number is not recognized.
        """
        if not self.packet_handler or not self.port_handler:
            raise RuntimeError("Driver not initialized for identify_model")

        try:
            # If model_number not provided, ping to get it
            if model_number is None:
                model_number, dxl_comm_result, dxl_error = self.packet_handler.ping(self.port_handler, motor_id)
                if dxl_comm_result != COMM_SUCCESS:
                    raise RuntimeError("Failed to ping motor to obtain model number")

            # Table-based lookup
            from .tables import select_model_for_number

            model_info = select_model_for_number(model_number, fw_major, fw_minor)
            if model_info is None:
                raise ValueError(f"Unknown Dynamixel model number: {model_number}")
            return model_info
        except Exception as e:
            logger.debug(f"identify_model exception for motor {motor_id}: {e}")
            raise

    def supported_models(self) -> list[MotorModelInfo]:
        """Return a list of supported MotorModelInfo derived from the typed tables."""
        from .tables import DYNAMIXEL_MODELS_LIST

        return list(DYNAMIXEL_MODELS_LIST)

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
            position = self._read_register(
                motor_id, DynamixelRegisters.ADDR_PRESENT_POSITION, DynamixelRegisters.LEN_PRESENT_POSITION
            )
            velocity = self._read_register(
                motor_id, DynamixelRegisters.ADDR_PRESENT_VELOCITY, DynamixelRegisters.LEN_PRESENT_VELOCITY
            )
            current = self._read_register(
                motor_id, DynamixelRegisters.ADDR_PRESENT_CURRENT, DynamixelRegisters.LEN_PRESENT_CURRENT
            )
            voltage = self._read_register(
                motor_id, DynamixelRegisters.ADDR_PRESENT_VOLTAGE, DynamixelRegisters.LEN_PRESENT_VOLTAGE
            )
            temperature = self._read_register(
                motor_id, DynamixelRegisters.ADDR_PRESENT_TEMPERATURE, DynamixelRegisters.LEN_PRESENT_TEMPERATURE
            )
            goal_position = self._read_register(
                motor_id, DynamixelRegisters.ADDR_GOAL_POSITION, DynamixelRegisters.LEN_GOAL_POSITION
            )

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
        Read telemetry from multiple motors efficiently using sync read.

        Args:
            motor_ids: List of motor IDs

        Returns:
            Dict mapping motor_id -> telemetry
        """
        if not self.group_sync_read or not self.port_handler or not self.packet_handler:
            # Fallback to individual reads
            result = {}
            for motor_id in motor_ids:
                telemetry = self.read_telemetry(motor_id)
                if telemetry:
                    result[motor_id] = telemetry
            return result

        result = {}
        try:
            # Clear sync read parameter storage
            self.group_sync_read.clearParam()

            # Add parameters for sync read
            for motor_id in motor_ids:
                # Add position parameter
                if not self.group_sync_read.addParam(
                    motor_id, DynamixelRegisters.ADDR_PRESENT_POSITION, DynamixelRegisters.LEN_PRESENT_POSITION
                ):
                    logger.warning(f"Failed to add position param for motor {motor_id}")
                    continue
                # Add velocity parameter
                if not self.group_sync_read.addParam(
                    motor_id, DynamixelRegisters.ADDR_PRESENT_VELOCITY, DynamixelRegisters.LEN_PRESENT_VELOCITY
                ):
                    logger.warning(f"Failed to add velocity param for motor {motor_id}")
                    continue
                # Add current parameter
                if not self.group_sync_read.addParam(
                    motor_id, DynamixelRegisters.ADDR_PRESENT_CURRENT, DynamixelRegisters.LEN_PRESENT_CURRENT
                ):
                    logger.warning(f"Failed to add current param for motor {motor_id}")
                    continue
                # Add voltage parameter
                if not self.group_sync_read.addParam(
                    motor_id, DynamixelRegisters.ADDR_PRESENT_VOLTAGE, DynamixelRegisters.LEN_PRESENT_VOLTAGE
                ):
                    logger.warning(f"Failed to add voltage param for motor {motor_id}")
                    continue
                # Add temperature parameter
                if not self.group_sync_read.addParam(
                    motor_id, DynamixelRegisters.ADDR_PRESENT_TEMPERATURE, DynamixelRegisters.LEN_PRESENT_TEMPERATURE
                ):
                    logger.warning(f"Failed to add temperature param for motor {motor_id}")
                    continue
                # Add goal position parameter
                if not self.group_sync_read.addParam(
                    motor_id, DynamixelRegisters.ADDR_GOAL_POSITION, DynamixelRegisters.LEN_GOAL_POSITION
                ):
                    logger.warning(f"Failed to add goal position param for motor {motor_id}")
                    continue

            # Perform sync read
            dxl_comm_result = self.group_sync_read.txRxPacket()
            if dxl_comm_result != COMM_SUCCESS:
                logger.error(f"Sync read failed: {self.packet_handler.getTxRxResult(dxl_comm_result)}")
                return result

            # Extract data for each motor
            for motor_id in motor_ids:
                try:
                    # Get data from sync read
                    position = self.group_sync_read.getData(
                        motor_id, DynamixelRegisters.ADDR_PRESENT_POSITION, DynamixelRegisters.LEN_PRESENT_POSITION
                    )
                    velocity = self.group_sync_read.getData(
                        motor_id, DynamixelRegisters.ADDR_PRESENT_VELOCITY, DynamixelRegisters.LEN_PRESENT_VELOCITY
                    )
                    current = self.group_sync_read.getData(
                        motor_id, DynamixelRegisters.ADDR_PRESENT_CURRENT, DynamixelRegisters.LEN_PRESENT_CURRENT
                    )
                    voltage = self.group_sync_read.getData(
                        motor_id, DynamixelRegisters.ADDR_PRESENT_VOLTAGE, DynamixelRegisters.LEN_PRESENT_VOLTAGE
                    )
                    temperature = self.group_sync_read.getData(
                        motor_id,
                        DynamixelRegisters.ADDR_PRESENT_TEMPERATURE,
                        DynamixelRegisters.LEN_PRESENT_TEMPERATURE,
                    )
                    goal_position = self.group_sync_read.getData(
                        motor_id, DynamixelRegisters.ADDR_GOAL_POSITION, DynamixelRegisters.LEN_GOAL_POSITION
                    )

                    # Convert raw values to physical units
                    position_rad = (position / 4096.0) * 2 * 3.14159265359
                    goal_position_rad = (goal_position / 4096.0) * 2 * 3.14159265359
                    velocity_rads = velocity if velocity < 2147483648 else velocity - 4294967296
                    current_ma = current if current < 32768 else current - 65536
                    voltage_v = voltage / 10.0
                    moving = abs(velocity_rads) > 0
                    load = min(100, int(abs(current_ma) / 10))

                    telemetry = MotorTelemetry(
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
                    result[motor_id] = telemetry

                except Exception as e:
                    logger.warning(f"Failed to extract telemetry for motor {motor_id}: {e}")

        except Exception as e:
            logger.error(f"Failed bulk telemetry read: {e}")
            # Fallback to individual reads
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
            success = self._write_register(
                motor_id, DynamixelRegisters.ADDR_GOAL_POSITION, position, DynamixelRegisters.LEN_GOAL_POSITION
            )

            # Write speed if provided
            if success and speed is not None:
                speed = max(0, min(2047, speed))  # Clamp speed to valid range
                success = self._write_register(
                    motor_id, DynamixelRegisters.ADDR_GOAL_VELOCITY, speed, DynamixelRegisters.LEN_GOAL_VELOCITY
                )

            return success
        except Exception as e:
            logger.error(f"Failed to set position for motor {motor_id}: {e}")
            return False

    def set_velocity(self, motor_id: int, velocity: int) -> bool:
        """
        Set motor target velocity.

        Args:
            motor_id: Motor ID
            velocity: Target velocity (raw velocity units)

        Returns:
            True if command sent successfully
        """
        try:
            # Clamp velocity to valid range
            velocity = max(-2048, min(2047, velocity))
            return self._write_register(
                motor_id, DynamixelRegisters.ADDR_GOAL_VELOCITY, velocity, DynamixelRegisters.LEN_GOAL_VELOCITY
            )
        except Exception as e:
            logger.error(f"Failed to set velocity for motor {motor_id}: {e}")
            return False

    def set_current(self, motor_id: int, current: int) -> bool:
        """
        Set motor target current.

        Args:
            motor_id: Motor ID
            current: Target current (raw current units)

        Returns:
            True if command sent successfully
        """
        try:
            # Clamp current to valid range
            current = max(-2048, min(2047, current))
            return self._write_register(
                motor_id, DynamixelRegisters.ADDR_GOAL_CURRENT, current, DynamixelRegisters.LEN_GOAL_CURRENT
            )
        except Exception as e:
            logger.error(f"Failed to set current for motor {motor_id}: {e}")
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
            return self._write_register(
                motor_id, DynamixelRegisters.ADDR_TORQUE_ENABLE, value, DynamixelRegisters.LEN_TORQUE_ENABLE
            )
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
        if not self.group_sync_write or not self.port_handler or not self.packet_handler:
            # Fallback to individual writes
            success = True
            for motor_id in motor_ids:
                if not self.set_torque(motor_id, enabled):
                    success = False
            return success

        try:
            # Clear sync write parameter storage
            self.group_sync_write.clearParam()

            value = 1 if enabled else 0

            # Add parameters for sync write
            for motor_id in motor_ids:
                if not self.group_sync_write.addParam(
                    motor_id, DynamixelRegisters.ADDR_TORQUE_ENABLE, DynamixelRegisters.LEN_TORQUE_ENABLE, value
                ):
                    logger.warning(f"Failed to add torque param for motor {motor_id}")
                    return False

            # Perform sync write
            dxl_comm_result = self.group_sync_write.txRxPacket()
            if dxl_comm_result != COMM_SUCCESS:
                logger.error(f"Sync write failed: {self.packet_handler.getTxRxResult(dxl_comm_result)}")
                return False

            return True

        except Exception as e:
            logger.error(f"Failed bulk torque set: {e}")
            # Fallback to individual writes
            success = True
            for motor_id in motor_ids:
                if not self.set_torque(motor_id, enabled):
                    success = False
            return success
