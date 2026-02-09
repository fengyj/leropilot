"""
Dynamixel Protocol 2.0 driver implementation.

Supports Dynamixel XL330, XL430, XC430, and XM430 motors.
"""

import logging
from functools import reduce

from dynamixel_sdk import (  # type: ignore[import-untyped]
    COMM_SUCCESS,
    GroupSyncRead,
    GroupSyncWrite,
    PacketHandler,
    PortHandler,
    Protocol1PacketHandler,
    Protocol2PacketHandler,
)

from leropilot.exceptions import MotorIdentificationError, OperationalError
from leropilot.models.hardware import MotorModelInfo, MotorTelemetry, PositionType

from ..base import BaseMotorDriver
from .tables import (
    DYNAMIXEL_MODELS_LIST,
    SIGNED_REGISTERS,
    DynamixelRegisters,
    dynamixel_supports_register,
    select_model_for_number,
)

logger = logging.getLogger(__name__)

# Protocol version
PROTOCOL_VERSION = 2.0


def decode_twos_complement(value: int, n_bytes: int) -> int:
    """Convert unsigned int to signed using two's complement."""
    n_bits = n_bytes * 8
    mask = (1 << n_bits) - 1
    value = value & mask
    if value & (1 << (n_bits - 1)):
        return value - (1 << n_bits)
    return value


def encode_twos_complement(value: int, n_bytes: int) -> int:
    """Convert signed int to unsigned using two's complement."""
    n_bits = n_bytes * 8
    if value < 0:
        return (1 << n_bits) + value
    return value


class DynamixelDriver(BaseMotorDriver[int]):
    """Driver for Dynamixel Protocol 2.0 motors"""

    def __init__(self, interface: str, baud_rate: int | None = None) -> None:
        """Initialize Dynamixel driver.

        Args:
            interface: Serial port (e.g., "COM11", "/dev/ttyUSB0")
            baud_rate: Serial baud rate (default: 1000000)
        """
        super().__init__(interface, baud_rate)
        self.port_handler: PortHandler | None = None
        self.packet_handler: Protocol1PacketHandler | Protocol2PacketHandler | None = None
        self.connected = False

        # Build register address -> (address, length) mapping for fast lookup
        self._register_map: dict[int, tuple[int, int]] = {}
        for reg_name, (reg_addr, reg_len) in vars(DynamixelRegisters).items():
            if not reg_name.startswith("_"):
                self._register_map[reg_addr] = (reg_addr, reg_len)

    def _get_register_length(self, address: int) -> int:
        """Get register length (in bytes) for a given address.

        Args:
            address: Register address

        Returns:
            Register length in bytes (1, 2, or 4)
        """
        if address in self._register_map:
            return self._register_map[address][1]
        # Default to 4-byte for unknown registers (common for Dynamixel)
        logger.warning(f"Unknown register address {address}, defaulting to 4-byte length")
        return 4

    def _get_register_address(self, name: str) -> int:
        """Return the hardware register address for a logical register `name`.

        Supported names: "position", "goal_position", "velocity", "current",
        "temperature", "torque_enable", "operation_mode". Raises NotImplementedError for unsupported names.
        """
        mapping = {
            "torque_enable": DynamixelRegisters.TORQUE_ENABLE[0],
            "position": DynamixelRegisters.PRESENT_POSITION[0],
            "goal_position": DynamixelRegisters.GOAL_POSITION[0],
            "velocity": DynamixelRegisters.PRESENT_VELOCITY[0],
            "current": DynamixelRegisters.PRESENT_CURRENT[0],
            "temperature": DynamixelRegisters.PRESENT_TEMPERATURE[0],
            "operation_mode": DynamixelRegisters.OPERATING_MODE[0],
        }
        try:
            return mapping[name]
        except KeyError as e:
            raise NotImplementedError(f"Named register '{name}' not supported by DynamixelDriver") from e

    def _decode_signed_register(self, address: int, value: int) -> int:
        """Decode register value using two's complement if in SIGNED_REGISTERS table.

        Args:
            address: Register address
            value: Raw unsigned register value

        Returns:
            Signed value if register uses two's complement, otherwise unchanged
        """
        if address in SIGNED_REGISTERS:
            n_bytes = SIGNED_REGISTERS[address]
            return decode_twos_complement(value, n_bytes)
        return value

    def _encode_signed_register(self, address: int, value: float) -> int:
        """Encode value using two's complement if in SIGNED_REGISTERS table.

        Args:
            address: Register address
            value: Signed value to encode

        Returns:
            Unsigned register value
        """
        int_value = int(value)
        if address in SIGNED_REGISTERS:
            n_bytes = SIGNED_REGISTERS[address]
            return encode_twos_complement(int_value, n_bytes)
        return int_value

    def _check_dxl_result(
        self, result: int, error: int, operation: str, motor_id: int, addr: int | None = None
    ) -> None:
        """Check Dynamixel operation result and raise OperationalError if failed."""
        if result != COMM_SUCCESS or error != 0:
            error_msg = f"{operation} failed for motor {motor_id}"
            if addr is not None:
                error_msg += f" at address {addr}"
            error_msg += f": result={result}, error={error}"
            logger.error(error_msg)
            raise OperationalError(error_msg)

    def _dxl_read_1byte(self, motor_id: int, addr: int) -> int:
        """Read a 1-byte register."""
        value, result, error = self.packet_handler.read1ByteTxRx(self.port_handler, motor_id, addr)
        self._check_dxl_result(result, error, "Read 1-byte", motor_id, addr)
        return value

    def _dxl_read_2byte(self, motor_id: int, addr: int) -> int:
        """Read a 2-byte register."""
        value, result, error = self.packet_handler.read2ByteTxRx(self.port_handler, motor_id, addr)
        self._check_dxl_result(result, error, "Read 2-byte", motor_id, addr)
        return value

    def _dxl_read_4byte(self, motor_id: int, addr: int) -> int:
        """Read a 4-byte register."""
        value, result, error = self.packet_handler.read4ByteTxRx(self.port_handler, motor_id, addr)
        self._check_dxl_result(result, error, "Read 4-byte", motor_id, addr)
        return value

    def _dxl_write_1byte(self, motor_id: int, addr: int, value: int) -> None:
        """Write a 1-byte register."""
        result, error = self.packet_handler.write1ByteTxRx(self.port_handler, motor_id, addr, value)
        self._check_dxl_result(result, error, "Write 1-byte", motor_id, addr)

    def _dxl_write_2byte(self, motor_id: int, addr: int, value: int) -> None:
        """Write a 2-byte register."""
        result, error = self.packet_handler.write2ByteTxRx(self.port_handler, motor_id, addr, value)
        self._check_dxl_result(result, error, "Write 2-byte", motor_id, addr)

    def _dxl_write_4byte(self, motor_id: int, addr: int, value: int) -> None:
        """Write a 4-byte register."""
        result, error = self.packet_handler.write4ByteTxRx(self.port_handler, motor_id, addr, value)
        self._check_dxl_result(result, error, "Write 4-byte", motor_id, addr)

    # ========== BaseMotorDriver Abstract Methods Implementation ==========

    def connect(self) -> None:
        """Connect to motor bus via serial port."""
        if self.connected:
            return

        self.port_handler = PortHandler(self.interface)
        self.packet_handler = PacketHandler(PROTOCOL_VERSION)

        if not self.port_handler.openPort():
            raise OperationalError(f"Failed to open port {self.interface}")

        baud_rate = self.baud_rate or 1000000
        if not self.port_handler.setBaudRate(baud_rate):
            self.port_handler.closePort()
            raise OperationalError(f"Failed to set baud rate to {baud_rate}")

        self.connected = True
        logger.info(f"Connected to {self.interface} at {baud_rate} baud")

    def disconnect(self) -> bool:
        """Disconnect from motor bus."""
        try:
            if self.connected and self.port_handler:
                self.port_handler.closePort()
                self.connected = False
                logger.info(f"Disconnected from {self.interface}")
            return True
        except Exception as e:
            logger.error(f"Error disconnecting from {self.interface}: {e}")
            return False

    def read_homing_offset(self, motor_id: int) -> float:
        """Read homing offset from motor."""
        addr, _ = DynamixelRegisters.HOMING_OFFSET
        return self.read_register(motor_id, addr)

    def write_homing_offset(self, motor_id: int, offset: float) -> None:
        """Write homing offset to motor."""
        addr, _ = DynamixelRegisters.HOMING_OFFSET
        self.write_register(motor_id, addr, offset)

    def bulk_read_homing_offsets(self, motor_ids: list[int]) -> dict[int, float]:
        """Bulk read homing offsets from multiple motors."""
        addr, _ = DynamixelRegisters.HOMING_OFFSET
        return self.bulk_read_registers(motor_ids, addr)

    def bulk_write_homing_offsets(self, motor_offsets: dict[int, float]) -> None:
        """Bulk write homing offsets to multiple motors."""
        addr, _ = DynamixelRegisters.HOMING_OFFSET
        self.bulk_write_registers(addr, motor_offsets)

    def read_position_range(self, motor_id: int) -> tuple[float, float]:
        """Read position range (min, max) from motor."""
        addr_min, _ = DynamixelRegisters.MIN_POSITION_LIMIT
        addr_max, _ = DynamixelRegisters.MAX_POSITION_LIMIT
        min_pos = self.read_register(motor_id, addr_min)
        max_pos = self.read_register(motor_id, addr_max)
        return (min_pos, max_pos)

    def write_position_range(self, motor_id: int, min_pos: float, max_pos: float) -> None:
        """Write position range (min, max) to motor."""
        addr_min, _ = DynamixelRegisters.MIN_POSITION_LIMIT
        addr_max, _ = DynamixelRegisters.MAX_POSITION_LIMIT
        self.write_register(motor_id, addr_min, min_pos)
        self.write_register(motor_id, addr_max, max_pos)

    def bulk_read_position_ranges(self, motor_ids: list[int]) -> dict[int, tuple[float, float]]:
        """Bulk read position ranges from multiple motors."""
        addr_min, _ = DynamixelRegisters.MIN_POSITION_LIMIT
        addr_max, _ = DynamixelRegisters.MAX_POSITION_LIMIT

        min_positions = self.bulk_read_registers(motor_ids, addr_min)
        max_positions = self.bulk_read_registers(motor_ids, addr_max)

        ranges: dict[int, tuple[float, float]] = {}
        for motor_id in motor_ids:
            min_pos = min_positions.get(motor_id, 0.0)
            max_pos = max_positions.get(motor_id, 0.0)
            ranges[motor_id] = (min_pos, max_pos)

        return ranges

    def bulk_write_position_ranges(self, motor_ranges: dict[int, tuple[float, float]]) -> None:
        """Bulk write position ranges to multiple motors."""
        addr_min, _ = DynamixelRegisters.MIN_POSITION_LIMIT
        addr_max, _ = DynamixelRegisters.MAX_POSITION_LIMIT

        min_positions: dict[int, float] = {}
        max_positions: dict[int, float] = {}

        for motor_id, (min_pos, max_pos) in motor_ranges.items():
            min_positions[motor_id] = min_pos
            max_positions[motor_id] = max_pos

        self.bulk_write_registers(addr_min, min_positions)
        self.bulk_write_registers(addr_max, max_positions)

    def read_position(self, motor_id: int) -> float:
        """Read current position from motor."""
        addr, _ = DynamixelRegisters.PRESENT_POSITION
        return self.read_register(motor_id, addr)

    def bulk_read_positions(self, motor_ids: list[int]) -> dict[int, float]:
        """Bulk read current positions from multiple motors."""
        addr, _ = DynamixelRegisters.PRESENT_POSITION
        return self.bulk_read_registers(motor_ids, addr)

    def read_goal_position(self, motor_id: int) -> float:
        """Read goal position from motor."""
        addr, _ = DynamixelRegisters.GOAL_POSITION
        return self.read_register(motor_id, addr)

    def bulk_read_goal_positions(self, motor_ids: list[int]) -> dict[int, float]:
        """Bulk read goal positions from multiple motors."""
        addr, _ = DynamixelRegisters.GOAL_POSITION
        return self.bulk_read_registers(motor_ids, addr)

    def write_goal_position(self, motor_id: int, position: float) -> None:
        """Write goal position to motor."""
        addr, _ = DynamixelRegisters.GOAL_POSITION
        self.write_register(motor_id, addr, position)

    def bulk_write_goal_positions(self, motor_positions: dict[int, float]) -> None:
        """Bulk write goal positions to multiple motors."""
        addr, _ = DynamixelRegisters.GOAL_POSITION
        self.bulk_write_registers(addr, motor_positions)

    def identify_model(
        self,
        motor_id: int,
        model_number: int | None = None,
        fw_major: int | None = None,
        fw_minor: int | None = None,
        raise_on_ambiguous: bool = False,
    ) -> MotorModelInfo:
        """Identify motor model."""
        # If model_number not provided, ping to get it
        if model_number is None:
            model_number, result, error = self.packet_handler.ping(self.port_handler, motor_id)
            if result != COMM_SUCCESS:
                logger.debug(f"Ping failed for motor {motor_id}")
                raise MotorIdentificationError(f"Ping failed for motor {motor_id}")

        # Table-based lookup
        model_info = select_model_for_number(model_number, fw_major, fw_minor)
        if model_info is None:
            raise ValueError(f"Unknown motor model number {model_number} for motor {motor_id}")

        return model_info

    def supported_models(self) -> list[MotorModelInfo]:
        """Return list of supported motor models."""
        return list(DYNAMIXEL_MODELS_LIST)

    def scan_motors(self, scan_range: list[int] | None = None) -> dict[int, MotorModelInfo]:
        """Scan motor bus and discover all motors."""
        if scan_range is None:
            scan_range = list(range(0, 253))

        discovered: dict[int, MotorModelInfo] = {}
        logger.info(f"Scanning {len(scan_range)} motor IDs...")

        for motor_id in scan_range:
            try:
                # Ping to get model number
                model_number, result, error = self.packet_handler.ping(self.port_handler, motor_id)
                if result != COMM_SUCCESS:
                    continue

                # Identify model
                model_info = self.identify_model(motor_id, model_number=model_number)
                discovered[motor_id] = model_info
                logger.info(f"Found motor {motor_id}: {model_info.model}")

            except MotorIdentificationError:
                pass  # No motor at this ID
            except Exception as e:
                logger.debug(f"Error scanning motor {motor_id}: {e}")

        logger.info(f"Scan complete. Found {len(discovered)} motors.")
        return discovered

    def read_register(self, motor_id: int, address: int) -> float:
        """Read a register value from a motor.

        Automatically determines register size and handles two's complement encoding.
        """
        # Get register length
        reg_len = self._get_register_length(address)

        # Read based on size
        if reg_len == 1:
            raw_value = self._dxl_read_1byte(motor_id, address)
        elif reg_len == 2:
            raw_value = self._dxl_read_2byte(motor_id, address)
        elif reg_len == 4:
            raw_value = self._dxl_read_4byte(motor_id, address)
        else:
            raise ValueError(f"Unsupported register length {reg_len} for address {address}")

        # Decode two's complement if applicable
        signed_value = self._decode_signed_register(address, raw_value)
        return float(signed_value)

    def write_register(self, motor_id: int, address: int, value: float) -> None:
        """Write a register value to a motor.

        Automatically determines register size and handles two's complement encoding.
        """
        # Encode with two's complement if applicable
        encoded_value = self._encode_signed_register(address, value)

        # Get register length
        reg_len = self._get_register_length(address)

        # Write based on size
        if reg_len == 1:
            self._dxl_write_1byte(motor_id, address, encoded_value & 0xFF)
        elif reg_len == 2:
            self._dxl_write_2byte(motor_id, address, encoded_value & 0xFFFF)
        elif reg_len == 4:
            self._dxl_write_4byte(motor_id, address, encoded_value & 0xFFFFFFFF)
        else:
            raise ValueError(f"Unsupported register length {reg_len} for address {address}")

    def bulk_read_registers(
        self,
        motor_ids: list[int],
        register_addr: int,
    ) -> dict[int, float]:
        """Read the same register from multiple motors using SyncRead."""
        if not motor_ids:
            return {}

        # Get register length
        reg_len = self._get_register_length(register_addr)

        # Use SyncRead
        group_sync_read = GroupSyncRead(self.port_handler, self.packet_handler, register_addr, reg_len)

        for motor_id in motor_ids:
            group_sync_read.addParam(motor_id)

        result = group_sync_read.txRxPacket()
        if result != COMM_SUCCESS:
            logger.warning(f"Sync read failed for register {register_addr}, using individual reads")
            # Fallback to base class implementation
            return super().bulk_read_registers(motor_ids, register_addr)

        # Parse results
        results: dict[int, float] = {}
        for motor_id in motor_ids:
            if group_sync_read.isAvailable(motor_id, register_addr, reg_len):
                raw_value = group_sync_read.getData(motor_id, register_addr, reg_len)
                signed_value = self._decode_signed_register(register_addr, raw_value)
                results[motor_id] = float(signed_value)

        group_sync_read.clearParam()
        return results

    def bulk_write_registers(
        self,
        motor_values: dict[int, float],
        register_addr: int,
    ) -> None:
        """Write the same register to multiple motors using SyncWrite."""
        if not motor_values:
            return

        # Get register length
        reg_len = self._get_register_length(register_addr)

        # Use SyncWrite
        group_sync_write = GroupSyncWrite(self.port_handler, self.packet_handler, register_addr, reg_len)

        for motor_id, value in motor_values.items():
            # Encode with two's complement if applicable
            encoded_value = self._encode_signed_register(register_addr, value)

            # Convert to byte array
            if reg_len == 1:
                data = [encoded_value & 0xFF]
            elif reg_len == 2:
                data = [
                    encoded_value & 0xFF,
                    (encoded_value >> 8) & 0xFF,
                ]
            elif reg_len == 4:
                data = [
                    encoded_value & 0xFF,
                    (encoded_value >> 8) & 0xFF,
                    (encoded_value >> 16) & 0xFF,
                    (encoded_value >> 24) & 0xFF,
                ]
            else:
                raise ValueError(f"Unsupported register length {reg_len}")

            if not group_sync_write.addParam(motor_id, data):
                logger.warning(f"Failed to add motor {motor_id} to sync write")

        result = group_sync_write.txPacket()
        if result != COMM_SUCCESS:
            logger.error(f"Sync write failed for register {register_addr}")
            raise OperationalError(f"Sync write failed: {result}")

        group_sync_write.clearParam()

    def read_telemetry(self, motor_id: int, model_info: MotorModelInfo) -> MotorTelemetry:
        """Read real-time telemetry from a single motor."""
        # Read position (required)
        addr_pos, _ = DynamixelRegisters.PRESENT_POSITION
        if not dynamixel_supports_register(model_info.model, addr_pos):
            raise OperationalError(f"Motor {motor_id} does not support position register")

        position = self.read_register(motor_id, addr_pos)

        # Read goal_position (optional)
        goal_position = None
        addr_goal, _ = DynamixelRegisters.GOAL_POSITION
        if dynamixel_supports_register(model_info.model, addr_goal):
            goal_position = self.read_register(motor_id, addr_goal)

        # Read velocity (optional)
        velocity_rad_s = None
        addr_vel, _ = DynamixelRegisters.PRESENT_VELOCITY
        if dynamixel_supports_register(model_info.model, addr_vel):
            velocity_rad_s = self.read_register_in_standard_unit(motor_id, model_info, addr_vel, "velocity")

        # Read current (optional)
        current_ma = None
        addr_cur, _ = DynamixelRegisters.PRESENT_CURRENT
        if dynamixel_supports_register(model_info.model, addr_cur):
            current_ma = self.read_register_in_standard_unit(motor_id, model_info, addr_cur, "current")

        # Read temperature (optional)
        temperature_c = None
        addr_temp, _ = DynamixelRegisters.PRESENT_TEMPERATURE
        if dynamixel_supports_register(model_info.model, addr_temp):
            temperature_c = self.read_register_in_standard_unit(motor_id, model_info, addr_temp, "temperature")

        # Read voltage (optional)
        voltage_v = None
        addr_volt, _ = DynamixelRegisters.PRESENT_VOLTAGE
        if dynamixel_supports_register(model_info.model, addr_volt):
            voltage_v = self.read_register_in_standard_unit(motor_id, model_info, addr_volt, "voltage")

        return MotorTelemetry(
            motor_id=motor_id,
            position=position,
            position_type=PositionType.RAW,
            goal_position=goal_position,
            velocity=velocity_rad_s if velocity_rad_s is not None else 0.0,
            current=current_ma,
            temperature=temperature_c,
            voltage=voltage_v,
            moving=velocity_rad_s is not None and abs(velocity_rad_s) > 1e-6,
            torque=None,
            error=0
        )

    def bulk_read_telemetry(self, motors: dict[int, MotorModelInfo]) -> dict[int, MotorTelemetry]:
        """Read telemetry from multiple motors using SyncRead."""
        if not motors:
            return {}

        # Read position (required)
        addr_pos, _ = DynamixelRegisters.PRESENT_POSITION
        if not reduce(lambda acc, model_info: acc and dynamixel_supports_register(model_info.model, addr_pos), motors.values(), True):
            raise OperationalError("One or more motors do not support position register")

        position = self.bulk_read_registers(list(motors.keys()), addr_pos)

        # Read goal_position (optional)
        goal_position = None
        addr_goal, _ = DynamixelRegisters.GOAL_POSITION
        if reduce(lambda acc, model_info: acc and dynamixel_supports_register(model_info.model, addr_goal), motors.values(), True):
            goal_position = self.bulk_read_registers(list(motors.keys()), addr_goal)

        # Read velocity (optional)
        velocity_rad_s = None
        addr_vel, _ = DynamixelRegisters.PRESENT_VELOCITY
        if reduce(lambda acc, model_info: acc and dynamixel_supports_register(model_info.model, addr_vel), motors.values(), True):
            velocity_rad_s = self.bulk_read_registers_in_standard_unit(motors, addr_vel, "velocity")

        # Read current (optional)
        current_ma = None
        addr_cur, _ = DynamixelRegisters.PRESENT_CURRENT
        if reduce(lambda acc, model_info: acc and dynamixel_supports_register(model_info.model, addr_cur), motors.values(), True):
            current_ma = self.bulk_read_registers_in_standard_unit(motors, addr_cur, "current")

        # Read temperature (optional)
        temperature_c = None
        addr_temp, _ = DynamixelRegisters.PRESENT_TEMPERATURE
        if reduce(lambda acc, model_info: acc and dynamixel_supports_register(model_info.model, addr_temp), motors.values(), True):
            temperature_c = self.bulk_read_registers_in_standard_unit(motors, addr_temp, "temperature")

        # Read voltage (optional)
        voltage_v = None
        addr_volt, _ = DynamixelRegisters.PRESENT_VOLTAGE
        if reduce(lambda acc, model_info: acc and dynamixel_supports_register(model_info.model, addr_volt), motors.values(), True):
            voltage_v = self.bulk_read_registers_in_standard_unit(motors, addr_volt, "voltage")

        return {
            mid: MotorTelemetry(
                motor_id=mid,
                position=position.get(mid),
                position_type=PositionType.RAW,
                goal_position=goal_position.get(mid) if goal_position else None,
                velocity=velocity_rad_s[mid] if velocity_rad_s else 0.0,
                current=current_ma.get(mid) if current_ma else None,
                temperature=temperature_c.get(mid) if temperature_c else None,
                moving=velocity_rad_s is not None and abs(velocity_rad_s.get(mid, 0.0)) > 1e-6,
                torque=None,
                voltage=voltage_v.get(mid) if voltage_v else None,
                error=0,
            )
            for mid in motors.keys()
        }
