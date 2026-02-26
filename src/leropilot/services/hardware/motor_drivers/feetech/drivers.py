"""
Feetech SCS servo driver implementation.

Supports Feetech STS3215 and SCS0009 servos using Feetech SDK.
"""

import logging
from functools import reduce

import scservo_sdk as scs

from leropilot.exceptions import OperationalError
from leropilot.models.hardware import MotorModelInfo, MotorTelemetry, PositionType

from ..base import BaseMotorDriver
from .tables import (
    SCS_STS_MODELS_LIST,
    SIGNED_REGISTERS,
    SCS_STS_Registers,
    feetech_supports_register,
    models_for_id,
)

logger = logging.getLogger(__name__)

# Protocol settings
PROTOCOL_END = 0  # Little-endian


class FeetechDriver(BaseMotorDriver[int]):
    """Driver for Feetech SCS servo motors using Feetech SDK"""

    def __init__(self, interface: str, baud_rate: int | None = None) -> None:
        """Initialize Feetech driver.

        Args:
            interface: Serial port (e.g., "COM11", "/dev/ttyUSB0")
            baud_rate: Serial baud rate (default: 1000000)
        """
        super().__init__(interface, baud_rate)
        self.port_handler = scs.PortHandler(self.interface)
        self.packet_handler = scs.PacketHandler(PROTOCOL_END)
        self.connected = False

        # Build register address -> (address, length) mapping for fast lookup
        self._register_map: dict[int, tuple[int, int]] = {}
        # Only include attributes that are (address, length) tuples and skip dunder/other attrs.
        for reg_name, reg_val in vars(SCS_STS_Registers).items():
            if reg_name.startswith("_"):
                continue
            if not isinstance(reg_val, tuple) or len(reg_val) != 2:
                continue
            reg_addr, reg_len = reg_val
            self._register_map[reg_addr] = (reg_addr, reg_len)

    def _get_register_length(self, address: int) -> int:
        """Get register length (in bytes) for a given address.

        Args:
            address: Register address

        Returns:
            Register length in bytes (1, 2, or 4)

        Raises:
            ValueError: If address is not found in register map
        """
        if address in self._register_map:
            return self._register_map[address][1]

        raise ValueError(f"Register address {address} not found in register map")

    def _get_register_address(self, name: str) -> int:
        """Return the hardware register address for a logical register `name`.

        Supported names: "position", "goal_position", "velocity", "current",
        "temperature", "torque_enable", "operation_mode". Raises NotImplementedError for unsupported names.
        """
        mapping = {
            "torque_enable": SCS_STS_Registers.TORQUE_ENABLE[0],
            "position": SCS_STS_Registers.PRESENT_POSITION[0],
            "goal_position": SCS_STS_Registers.GOAL_POSITION[0],
            "velocity": SCS_STS_Registers.PRESENT_VELOCITY[0],
            "current": SCS_STS_Registers.PRESENT_CURRENT[0],
            "temperature": SCS_STS_Registers.PRESENT_TEMPERATURE[0],
            "operation_mode": SCS_STS_Registers.OPERATING_MODE[0],
        }
        try:
            return mapping[name]
        except KeyError as e:
            raise NotImplementedError(f"Named register '{name}' not supported by FeetechDriver") from e

    def _decode_signed_register(self, value: int, addr: int) -> int:
        """Decode register value using sign-magnitude encoding if in SIGNED_REGISTERS table.

        Feetech motors use sign-magnitude encoding, not two's complement.

        Args:
            value: Raw unsigned register value
            addr: Register address

        Returns:
            Signed value if register uses sign-magnitude, otherwise unchanged
        """
        if addr in SIGNED_REGISTERS:
            sign_bit = SIGNED_REGISTERS[addr]
            sign_mask = 1 << sign_bit
            magnitude_mask = sign_mask - 1
            if value & sign_mask:  # Negative
                return -(value & magnitude_mask)
            return value & magnitude_mask
        return value

    def _encode_signed_register(self, value: float, addr: int) -> int:
        """Encode value using sign-magnitude encoding if in SIGNED_REGISTERS table.

        Feetech motors use sign-magnitude encoding, not two's complement.

        Args:
            value: Signed value to encode
            addr: Register address

        Returns:
            Unsigned register value
        """
        int_value = int(value)
        if addr in SIGNED_REGISTERS:
            sign_bit = SIGNED_REGISTERS[addr]
            sign_mask = 1 << sign_bit
            magnitude_mask = sign_mask - 1
            if int_value < 0:
                return sign_mask | (abs(int_value) & magnitude_mask)
            return int_value & magnitude_mask
        return int_value

    def _check_sdk_result(
        self, result: int, error: int, operation: str, motor_id: int, addr: int | None = None
    ) -> None:
        """Check SDK operation result and raise OperationalError if failed.

        Enhances logs with the SDK constant name (e.g., COMM_RX_TIMEOUT) when available
        to make diagnostics easier.
        """
        if result != scs.COMM_SUCCESS or error != 0:
            # Try to map result code to friendly name from scservo_sdk (COMM_* constants)
            result_name = None
            for name in dir(scs):
                if name.startswith("COMM_"):
                    try:
                        if getattr(scs, name) == result:
                            result_name = name
                            break
                    except Exception:
                        continue

            error_msg = f"{operation} failed for motor {motor_id}"
            if addr is not None:
                error_msg += f" at address {addr}"
            if result_name:
                error_msg += f": result={result} ({result_name}), error={error}"
            else:
                error_msg += f": result={result}, error={error}"

            raise OperationalError(error_msg)

    def _feetech_read_byte(self, motor_id: int, addr: int) -> int:
        """Read a single byte register."""

        value, result, error = self.packet_handler.read1ByteTxRx(self.port_handler, motor_id, addr)
        self._check_sdk_result(result, error, "Read byte", motor_id, addr)
        return value

    def _feetech_read_word(self, motor_id: int, addr: int) -> int:
        """Read a 2-byte register."""

        value, result, error = self.packet_handler.read2ByteTxRx(self.port_handler, motor_id, addr)
        self._check_sdk_result(result, error, "Read word", motor_id, addr)
        return value

    def _feetech_read_dword(self, motor_id: int, addr: int) -> int:
        """Read a 4-byte register."""

        value, result, error = self.packet_handler.read4ByteTxRx(self.port_handler, motor_id, addr)
        self._check_sdk_result(result, error, "Read dword", motor_id, addr)
        return value

    def _feetech_write_byte(self, motor_id: int, addr: int, value: int) -> None:
        """Write a single byte register."""

        result, error = self.packet_handler.write1ByteTxRx(self.port_handler, motor_id, addr, value)
        self._check_sdk_result(result, error, "Write byte", motor_id, addr)

    def _feetech_write_word(self, motor_id: int, addr: int, value: int) -> None:
        """Write a 2-byte register."""

        result, error = self.packet_handler.write2ByteTxRx(self.port_handler, motor_id, addr, value)
        self._check_sdk_result(result, error, "Write word", motor_id, addr)

    def _feetech_write_dword(self, motor_id: int, addr: int, value: int) -> None:
        """Write a 4-byte register."""

        result, error = self.packet_handler.write4ByteTxRx(self.port_handler, motor_id, addr, value)
        self._check_sdk_result(result, error, "Write dword", motor_id, addr)

    def _read_model_and_fw(self, motor_id: int) -> tuple[int, int | None, int | None]:
        """Read model number and firmware version.

        Returns:
            (model_number, fw_major, fw_minor)
            firmware values may be None if read fails
        """
        addr, _ = SCS_STS_Registers.MODEL_NUMBER
        model_number = int(self.read_register(motor_id, addr))

        fw_major = None
        fw_minor = None
        try:
            addr, _ = SCS_STS_Registers.FIRMWARE_MAJOR
            fw_word = int(self.read_register(motor_id, addr))
            fw_major = (fw_word >> 8) & 0xFF
            fw_minor = fw_word & 0xFF
        except OperationalError:
            logger.debug(f"Could not read firmware version for motor {motor_id}")

        return model_number, fw_major, fw_minor

    # ========== BaseMotorDriver Abstract Methods Implementation ==========

    def connect(self) -> None:
        """Connect to motor bus via serial port."""
        if self.connected:
            return

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
        """Read homing offset register."""
        addr, _ = SCS_STS_Registers.HOMING_OFFSET
        return self.read_register(motor_id, addr)

    def write_homing_offset(self, motor_id: int, offset: float) -> None:
        """Write homing offset register."""
        addr, _ = SCS_STS_Registers.HOMING_OFFSET
        self.write_register(motor_id, addr, offset)

    def bulk_read_homing_offsets(
        self,
        motor_ids: list[int],
    ) -> dict[int, float]:
        """Read homing offset register from multiple motors using SyncRead."""
        addr, _ = SCS_STS_Registers.HOMING_OFFSET
        return self.bulk_read_registers(motor_ids, addr)

    def bulk_write_homing_offsets(
        self,
        motor_values: dict[int, float],
    ) -> None:
        """Write homing offset register to multiple motors using SyncWrite."""
        addr, _ = SCS_STS_Registers.HOMING_OFFSET
        self.bulk_write_registers(addr, motor_values)

    def read_position_range(self, motor_id: int) -> tuple[float, float]:
        """Read position range (min, max) registers."""
        addr_min, _ = SCS_STS_Registers.MIN_POSITION_LIMIT
        addr_max, _ = SCS_STS_Registers.MAX_POSITION_LIMIT
        min_pos = self.read_register(motor_id, addr_min)
        max_pos = self.read_register(motor_id, addr_max)
        return (min_pos, max_pos)

    def write_position_range(self, motor_id: int, min_pos: float, max_pos: float) -> None:
        """Write position range (min, max) registers."""
        addr_min, _ = SCS_STS_Registers.MIN_POSITION_LIMIT
        addr_max, _ = SCS_STS_Registers.MAX_POSITION_LIMIT
        self.write_register(motor_id, addr_min, min_pos)
        self.write_register(motor_id, addr_max, max_pos)

    def bulk_read_position_ranges(
        self,
        motor_ids: list[int],
    ) -> dict[int, tuple[float, float]]:
        """Read position range (min, max) registers from multiple motors using SyncRead."""
        addr_min, _ = SCS_STS_Registers.MIN_POSITION_LIMIT
        addr_max, _ = SCS_STS_Registers.MAX_POSITION_LIMIT
        min_positions = self.bulk_read_registers(motor_ids, addr_min)
        max_positions = self.bulk_read_registers(motor_ids, addr_max)
        return {motor_id: (min_positions[motor_id], max_positions[motor_id]) for motor_id in motor_ids}

    def bulk_write_position_ranges(
        self,
        motor_values: dict[int, tuple[float, float]],
    ) -> None:
        """Write position range (min, max) registers to multiple motors using SyncWrite."""
        addr_min, _ = SCS_STS_Registers.MIN_POSITION_LIMIT
        addr_max, _ = SCS_STS_Registers.MAX_POSITION_LIMIT
        min_values = {motor_id: vals[0] for motor_id, vals in motor_values.items()}
        max_values = {motor_id: vals[1] for motor_id, vals in motor_values.items()}
        self.bulk_write_registers(addr_min, min_values)
        self.bulk_write_registers(addr_max, max_values)

    def read_position(self, motor_id: int) -> float:
        """Read motor position."""
        addr, _ = SCS_STS_Registers.PRESENT_POSITION
        return self.read_register(motor_id, addr)

    def bulk_read_positions(
        self,
        motor_ids: list[int],
    ) -> dict[int, float]:
        """Read motor positions from multiple motors using SyncRead."""
        addr, _ = SCS_STS_Registers.PRESENT_POSITION
        return self.bulk_read_registers(motor_ids, addr)

    def read_goal_position(self, motor_id: int) -> float:
        """Read motor goal position."""
        addr, _ = SCS_STS_Registers.GOAL_POSITION
        return self.read_register(motor_id, addr)

    def bulk_read_goal_positions(
        self,
        motor_ids: list[int],
    ) -> dict[int, float]:
        """Read motor goal positions from multiple motors using SyncRead."""
        addr, _ = SCS_STS_Registers.GOAL_POSITION
        return self.bulk_read_registers(motor_ids, addr)

    def write_goal_position(self, motor_id: int, position: float) -> None:
        """Write motor goal position."""
        addr, _ = SCS_STS_Registers.GOAL_POSITION
        self.write_register(motor_id, addr, position)

    def bulk_write_goal_positions(
        self,
        motor_values: dict[int, float],
    ) -> None:
        """Write motor goal positions to multiple motors using SyncWrite."""
        addr, _ = SCS_STS_Registers.GOAL_POSITION
        self.bulk_write_registers(addr, motor_values)

    def identify_model(
        self,
        motor_id: int,
        model_number: int | None = None,
        fw_major: int | None = None,
        fw_minor: int | None = None,
        raise_on_ambiguous: bool = False,
    ) -> MotorModelInfo:
        """Identify motor model."""
        # Read model/fw if not provided
        if model_number is None:
            model_number, fw_major, fw_minor = self._read_model_and_fw(motor_id)
        elif fw_major is None or fw_minor is None:
            _, fw_major, fw_minor = self._read_model_and_fw(motor_id)

        # Find candidates
        candidates = models_for_id(model_number)
        if not candidates:
            raise ValueError(f"Unknown motor model number {model_number} (0x{model_number:04X}) for motor {motor_id}")

        # Prefer base model (no variant)
        for c in candidates:
            if c.variant is None:
                return c

        # Return first candidate if no base model found
        return candidates[0].model_copy()

    def supported_models(self) -> list[MotorModelInfo]:
        """Return list of supported motor models."""
        return SCS_STS_MODELS_LIST.copy()

    def scan_motors(self, scan_range: list[int] | None = None) -> dict[int, MotorModelInfo]:
        """Scan motor bus and discover all motors."""
        if scan_range is None:
            scan_range = list(range(1, 254))

        discovered: dict[int, MotorModelInfo] = {}
        logger.info(f"Scanning {len(scan_range)} motor IDs...")

        for motor_id in scan_range:
            try:

                # Identify model
                model_info = self.identify_model(
                    motor_id,
                )
                discovered[motor_id] = model_info
                logger.info(f"Found motor {motor_id}: {model_info.model}")

            except OperationalError:
                pass  # No motor at this ID
            except Exception as e:
                logger.debug(f"Error scanning motor {motor_id}: {e}")

        logger.info(f"Scan complete. Found {len(discovered)} motors.")
        return discovered

    def read_register(self, motor_id: int, address: int) -> float:
        """Read a register value from a motor.

        Automatically determines register size and handles sign-magnitude encoding.
        """
        # Get register length
        reg_len = self._get_register_length(address)

        # Read based on size
        if reg_len == 1:
            raw_value = self._feetech_read_byte(motor_id, address)
        elif reg_len == 2:
            raw_value = self._feetech_read_word(motor_id, address)
        elif reg_len == 4:
            raw_value = self._feetech_read_dword(motor_id, address)
        else:
            raise ValueError(f"Unsupported register length {reg_len} for address {address}")

        # Mask to register width to avoid sign-extension artifacts from SDK values
        mask = (1 << (reg_len * 8)) - 1
        raw_value &= mask

        # Decode sign-magnitude if applicable
        signed_value = self._decode_signed_register(raw_value, address)
        return float(signed_value)

    def write_register(self, motor_id: int, address: int, value: float) -> None:
        """Write a register value to a motor.

        Automatically determines register size and handles sign-magnitude encoding.
        """
        # Encode with sign-magnitude if applicable
        encoded_value = self._encode_signed_register(value, address)

        # Get register length
        reg_len = self._get_register_length(address)

        # Write based on size
        if reg_len == 1:
            self._feetech_write_byte(motor_id, address, encoded_value & 0xFF)
        elif reg_len == 2:
            self._feetech_write_word(motor_id, address, encoded_value & 0xFFFF)
        elif reg_len == 4:
            self._feetech_write_dword(motor_id, address, encoded_value & 0xFFFFFFFF)
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
        group_sync_read = scs.GroupSyncRead(self.port_handler, self.packet_handler, register_addr, reg_len)

        for motor_id in motor_ids:
            group_sync_read.addParam(motor_id)

        result = group_sync_read.txRxPacket()
        if result != scs.COMM_SUCCESS:
            logger.warning(f"Sync read failed for register {register_addr}, using individual reads")
            # Fallback to base class implementation
            return super().bulk_read_registers(motor_ids, register_addr)

        # Parse results
        results: dict[int, float] = {}
        for motor_id in motor_ids:
            if group_sync_read.isAvailable(motor_id, register_addr, reg_len):
                raw_value = group_sync_read.getData(motor_id, register_addr, reg_len)
                # Mask to register width to avoid sign-extension artifacts
                mask = (1 << (reg_len * 8)) - 1
                raw_value &= mask
                signed_value = self._decode_signed_register(raw_value, register_addr)
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
        group_sync_write = scs.GroupSyncWrite(self.port_handler, self.packet_handler, register_addr, reg_len)

        for motor_id, value in motor_values.items():
            # Encode with sign-magnitude if applicable
            encoded_value = self._encode_signed_register(value, register_addr)

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
        if result != scs.COMM_SUCCESS:
            logger.error(f"Sync write failed for register {register_addr}")
            raise OperationalError(f"Sync write failed: {result}")

        group_sync_write.clearParam()

    def read_telemetry(self, motor_id: int, model_info: MotorModelInfo) -> MotorTelemetry:
        """Read real-time telemetry from a single motor."""
        # Read position (required)
        addr_pos, _ = SCS_STS_Registers.PRESENT_POSITION
        if not feetech_supports_register(model_info.model, addr_pos):
            raise OperationalError(f"Motor {motor_id} does not support position register")

        position = self.read_register(motor_id, addr_pos)

        # Read goal_position (optional)
        goal_position = None
        addr_goal, _ = SCS_STS_Registers.GOAL_POSITION
        if feetech_supports_register(model_info.model, addr_goal):
            goal_position = self.read_register(motor_id, addr_goal)

        # Read velocity (optional)
        velocity_rad_s = None
        addr_vel, _ = SCS_STS_Registers.PRESENT_VELOCITY
        if feetech_supports_register(model_info.model, addr_vel):
            velocity_rad_s = self.read_register_in_standard_unit(motor_id, model_info, addr_vel, "velocity")

        # Read current (optional)
        current_ma = None
        addr_cur, _ = SCS_STS_Registers.PRESENT_CURRENT
        if feetech_supports_register(model_info.model, addr_cur):
            current_ma = self.read_register_in_standard_unit(motor_id, model_info, addr_cur, "current")

        # Read temperature (optional)
        temperature_c = None
        addr_temp, _ = SCS_STS_Registers.PRESENT_TEMPERATURE
        if feetech_supports_register(model_info.model, addr_temp):
            temperature_c = self.read_register_in_standard_unit(motor_id, model_info, addr_temp, "temperature")

        # Read voltage (optional)
        voltage_v = None
        addr_volt, _ = SCS_STS_Registers.PRESENT_VOLTAGE
        if feetech_supports_register(model_info.model, addr_volt):
            voltage_v = self.read_register_in_standard_unit(motor_id, model_info, addr_volt, "voltage")

        return MotorTelemetry(
            motor_id=motor_id,
            position=position,
            position_type=PositionType.RAW,
            goal_position=goal_position,
            velocity=velocity_rad_s or 0.0,
            current=current_ma,
            temperature=temperature_c,
            voltage=voltage_v,
            torque=None,
            moving=bool(velocity_rad_s and abs(velocity_rad_s) > 1e-3),
            error=0,
        )

    def bulk_read_telemetry(self, motors: dict[int, MotorModelInfo]) -> dict[int, MotorTelemetry]:
        """Read telemetry from multiple motors using SyncRead."""
        if not motors:
            return {}

        # Read position (required)
        addr_pos, _ = SCS_STS_Registers.PRESENT_POSITION
        if not reduce(lambda acc, model_info: acc and feetech_supports_register(model_info.model, addr_pos), motors.values(), True):
            raise OperationalError("One or more motors do not support position register")

        position = self.bulk_read_registers(list(motors.keys()), addr_pos)

        # Read goal_position (optional)
        goal_position = None
        addr_goal, _ = SCS_STS_Registers.GOAL_POSITION
        if reduce(lambda acc, model_info: acc and feetech_supports_register(model_info.model, addr_goal), motors.values(), True):
            goal_position = self.bulk_read_registers(list(motors.keys()), addr_goal)

        # Read velocity (optional)
        velocity_rad_s = None
        addr_vel, _ = SCS_STS_Registers.PRESENT_VELOCITY
        if reduce(lambda acc, model_info: acc and feetech_supports_register(model_info.model, addr_vel), motors.values(), True):
            velocity_rad_s = self.bulk_read_registers_in_standard_unit(motors, addr_vel, "velocity")

        # Read current (optional)
        current_ma = None
        addr_cur, _ = SCS_STS_Registers.PRESENT_CURRENT
        if reduce(lambda acc, model_info: acc and feetech_supports_register(model_info.model, addr_cur), motors.values(), True):
            current_ma = self.bulk_read_registers_in_standard_unit(motors, addr_cur, "current")

        # Read temperature (optional)
        temperature_c = None
        addr_temp, _ = SCS_STS_Registers.PRESENT_TEMPERATURE
        if reduce(lambda acc, model_info: acc and feetech_supports_register(model_info.model, addr_temp), motors.values(), True):
            temperature_c = self.bulk_read_registers_in_standard_unit(motors, addr_temp, "temperature")

        # Read voltage (optional)
        voltage_v = None
        addr_volt, _ = SCS_STS_Registers.PRESENT_VOLTAGE
        if reduce(lambda acc, model_info: acc and feetech_supports_register(model_info.model, addr_volt), motors.values(), True):
            voltage_v = self.bulk_read_registers_in_standard_unit(motors, addr_volt, "voltage")

        return {
            mid: MotorTelemetry(
                motor_id=mid,
                position=position.get(mid),
                position_type=PositionType.RAW,
                goal_position=goal_position.get(mid) if goal_position else None,
                velocity=velocity_rad_s.get(mid, 0.0) if velocity_rad_s is not None else 0.0,
                current=current_ma.get(mid) if current_ma else None,
                temperature=temperature_c.get(mid) if temperature_c else None,
                voltage=voltage_v.get(mid) if voltage_v else None,
                torque=None,
                moving=bool(velocity_rad_s and abs(velocity_rad_s.get(mid, 0.0)) > 1e-3),
                error=0,
            )
            for mid in motors.keys()
        }
