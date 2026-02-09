"""
Dynamixel Protocol 2.0 driver implementation.

Supports Dynamixel XL330, XL430, XC430, and XM430 motors.
Uses ROBOTIS dynamixel-sdk for protocol handling.
"""

import logging

from dynamixel_sdk import (
    COMM_SUCCESS,
    GroupSyncRead,
    GroupSyncWrite,
    PacketHandler,
    PortHandler,
)

from leropilot.exceptions import MotorIdentificationError, OperationalError
from leropilot.models.hardware import MotorModelInfo, MotorTelemetry, PositionType

from ..base import BaseMotorDriver
from .tables import SIGNED_REGISTERS, DynamixelRegisters, dynamixel_supports_register


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


logger = logging.getLogger(__name__)

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
        # Bulk read/write removed: prefer GroupSyncRead per-register approach for
        # compatibility and simplicity.
        # (GroupBulkRead/GroupBulkWrite intentionally omitted.)

    def connect(self) -> None:
        """Connect to motor bus via serial port.

        Raises:
            OperationalError: If connection fails.
        """
        try:
            self.port_handler = PortHandler(self.interface)
            self.packet_handler = PacketHandler(PROTOCOL_VERSION)

            if not self.port_handler.openPort():
                logger.error(f"Failed to open port {self.interface}")
                raise OperationalError(
                    i18n_key="hardware.motor_device.connect_failed",
                    retriable=True,
                    interface=self.interface,
                )

            # Use a default baud rate if none provided
            baud_to_set = int(self.baud_rate or 1000000)
            if not self.port_handler.setBaudRate(baud_to_set):
                logger.error(f"Failed to set baud rate {baud_to_set}")
                self.port_handler.closePort()
                raise OperationalError(
                    i18n_key="hardware.motor_device.connect_failed",
                    retriable=True,
                    interface=self.interface,
                )

            # Initialize group handlers for bulk operations
            self.group_sync_read = GroupSyncRead(self.port_handler, self.packet_handler, 0, 0)
            self.group_sync_write = GroupSyncWrite(self.port_handler, self.packet_handler, 0, 0)
            # GroupBulkRead/GroupBulkWrite intentionally omitted; use GroupSyncRead per-register approach.

            self.connected = True
            logger.info(f"Connected to Dynamixel motor bus on {self.interface} @ {self.baud_rate} baud")
        except OperationalError:
            raise
        except Exception as e:
            logger.error(f"Failed to connect to Dynamixel motor bus: {e}")
            self.connected = False
            raise OperationalError(
                i18n_key="hardware.motor_device.connect_failed",
                retriable=True,
                interface=self.interface,
            ) from e

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

    def scan_motors(self, scan_range: list[int] | None = None) -> dict[int, MotorModelInfo]:
        """
        Scan motor bus and discover all motors using optimized batch ping.

        Performance: Scans in batches of 20 with reduced overhead for ~2-3x speedup.

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

        # Scan in batches to provide progress feedback and reduce overhead
        batch_size = 20
        for i in range(0, len(scan_range), batch_size):
            batch = scan_range[i : i + batch_size]
            logger.debug(f"Scanning batch: motor IDs {batch[0]}-{batch[-1]}")

            for motor_id in batch:
                try:
                    # Use identify_model to consolidate model identification logic
                    model_info = self.identify_model(motor_id)
                    discovered[motor_id] = model_info
                    logger.info(f"Found motor {motor_id}: {model_info.model}")
                except MotorIdentificationError as e:
                    logger.debug(f"Scan exception for motor {motor_id}: {e}")
                except Exception as e:
                    logger.debug(f"Scan exception for motor {motor_id}: {e}")

        logger.info(f"Scan complete: found {len(discovered)} motors")
        return discovered

    def _read_1byte(self, motor_id: int, address: int) -> int:
        """Read a 1-byte register value from the motor."""
        result, dxl_comm_result, dxl_error = self.packet_handler.read1ByteTxRx(self.port_handler, motor_id, address)
        if dxl_comm_result != COMM_SUCCESS:
            raise OperationalError(
                i18n_key="hardware.motor_device.read_failed",
                retriable=True,
                interface=self.interface,
                motor_id=motor_id,
                register=address,
            )
        if dxl_error != 0:
            logger.warning(f"Motor {motor_id} returned error {dxl_error} reading address {address}")
        return result

    def _read_2byte(self, motor_id: int, address: int) -> int:
        """Read a 2-byte register value from the motor."""
        result, dxl_comm_result, dxl_error = self.packet_handler.read2ByteTxRx(self.port_handler, motor_id, address)
        if dxl_comm_result != COMM_SUCCESS:
            raise OperationalError(
                i18n_key="hardware.motor_device.read_failed",
                retriable=True,
                interface=self.interface,
                motor_id=motor_id,
                register=address,
            )
        if dxl_error != 0:
            logger.warning(f"Motor {motor_id} returned error {dxl_error} reading address {address}")
        return result

    def _read_4byte(self, motor_id: int, address: int) -> int:
        """Read a 4-byte register value from the motor."""
        result, dxl_comm_result, dxl_error = self.packet_handler.read4ByteTxRx(self.port_handler, motor_id, address)
        if dxl_comm_result != COMM_SUCCESS:
            raise OperationalError(
                i18n_key="hardware.motor_device.read_failed",
                retriable=True,
                interface=self.interface,
                motor_id=motor_id,
                register=address,
            )
        if dxl_error != 0:
            logger.warning(f"Motor {motor_id} returned error {dxl_error} reading address {address}")
        return result

    def read_register(self, motor_id: int, address: int) -> float:
        """Read a register value from a motor.

        Automatically determines register size and handles signed conversion.

        Args:
            motor_id: Motor ID
            address: Register address

        Returns:
            Register value as float
        """
        # Get register length
        length = self._get_register_length(address)

        try:
            if length == 1:
                raw_value = self._read_1byte(motor_id, address)
            elif length == 2:
                raw_value = self._read_2byte(motor_id, address)
            elif length == 4:
                raw_value = self._read_4byte(motor_id, address)
            else:
                raise ValueError(f"Unsupported register length: {length}")

            # Decode signed if needed
            signed_value = self._decode_signed_register(address, raw_value)
            return float(signed_value) if signed_value is not None else 0.0
        except Exception as e:
            logger.debug(f"Failed to read register {address} from motor {motor_id}: {e}")
            raise

    # NOTE: `_read_register` removed — call size-specific methods directly.
    # Centralized dispatcher added little value and hid communication errors.

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
        try:
            # If model_number not provided, ping to get it
            if model_number is None:
                model_number, dxl_comm_result, dxl_error = self.packet_handler.ping(self.port_handler, motor_id)
                if dxl_comm_result != COMM_SUCCESS:
                    logger.debug(f"Ping failed for motor {motor_id}: {dxl_comm_result}")
                    # Treat ping failure as "motor not present" — raise identification error that callers may ignore
                    raise MotorIdentificationError(
                        i18n_key="hardware.motor_device.identification_failed",
                        retriable=False,
                        interface=self.interface,
                        motor_id=motor_id,
                    )

            # Table-based lookup
            from .tables import select_model_for_number

            model_info = select_model_for_number(model_number, fw_major, fw_minor)
            if model_info is None:
                raise MotorIdentificationError(
                    i18n_key="hardware.motor_device.unknown_model",
                    retriable=False,
                    interface=self.interface,
                    motor_id=motor_id,
                    data={"model_number": model_number},
                )
            return model_info
        except Exception as e:
            logger.debug(f"identify_model exception for motor {motor_id}: {e}")
            raise

    def _read_position(self, motor_id: int, model_info: MotorModelInfo) -> int | None:
        """Read present position (4 bytes).

        **Deprecated**: This internal helper is scheduled for removal. Prefer
        ``read_position`` which returns position in standard units (radians).

        Returns:
            Raw register value (int) or None if register unsupported for model.
        """
        if not dynamixel_supports_register(model_info.model, DynamixelRegisters.PRESENT_POSITION[0]):
            return None
        return self._read_4byte(motor_id, DynamixelRegisters.PRESENT_POSITION[0])

    def _read_velocity(self, motor_id: int, model_info: MotorModelInfo) -> int | None:
        """Read present velocity (4 bytes) in raw hardware units.

        Returns:
            Raw velocity value (int) or None if register unsupported for model.
        """
        if not dynamixel_supports_register(model_info.model, DynamixelRegisters.PRESENT_VELOCITY[0]):
            return None
        return self._read_4byte(motor_id, DynamixelRegisters.PRESENT_VELOCITY[0])

    def _read_current(self, motor_id: int, model_info: MotorModelInfo) -> int | None:
        """Read present current (2 bytes).

        Returns:
            Raw register value (int) or None if register unsupported for model.
        """
        if not dynamixel_supports_register(model_info.model, DynamixelRegisters.PRESENT_CURRENT[0]):
            return None
        return self._read_2byte(motor_id, DynamixelRegisters.PRESENT_CURRENT[0])

    def _read_voltage(self, motor_id: int, model_info: MotorModelInfo) -> int | None:
        """Read present voltage (2 bytes).

        Returns:
            Raw register value (int) or None if register unsupported for model.
        """
        if not dynamixel_supports_register(model_info.model, DynamixelRegisters.PRESENT_VOLTAGE[0]):
            return None
        return self._read_2byte(motor_id, DynamixelRegisters.PRESENT_VOLTAGE[0])

    def _read_temperature(self, motor_id: int, model_info: MotorModelInfo) -> int:
        """Read present temperature (1 byte).

        Returns:
            Temperature raw value (int) or 0 if unsupported.
        """
        if not dynamixel_supports_register(model_info.model, DynamixelRegisters.PRESENT_TEMPERATURE[0]):
            # Some models may not provide temperature sensors; treat as 0
            return 0
        return self._read_1byte(motor_id, DynamixelRegisters.PRESENT_TEMPERATURE[0])

    def _read_goal_position(self, motor_id: int, model_info: MotorModelInfo) -> int | None:
        """Read goal position (4 bytes). Returns None if unsupported or failed.

        Assumes `model_info` is always provided by callers.
        """
        if not dynamixel_supports_register(model_info.model, DynamixelRegisters.GOAL_POSITION[0]):
            return None
        return self._read_4byte(motor_id, DynamixelRegisters.GOAL_POSITION[0])

    # ------------------------------------------------------------------
    # Value-level implementations (position, velocity, current, torque)
    # ------------------------------------------------------------------

    def read_position(self, motor_id: int, model_info: MotorModelInfo) -> float | None:
        """Read motor position in radians (standard units) using `read_value`."""
        # Use value-level API (position conversion handled by model_info)
        return self.read_value(
            motor_id,
            model_info,
            DynamixelRegisters.PRESENT_POSITION[0],
            DynamixelRegisters.PRESENT_POSITION[1],
            "position",
        )

    def write_position(
        self, motor_id: int, model_info: MotorModelInfo, position: float, velocity: float | None = None
    ) -> bool:
        """Write motor target position in radians using `write_value` (preferred).

        If an optional `velocity` is provided, write velocity as well via `write_value`.
        Exceptions from the underlying write operations propagate to the caller.
        """
        ok = self.write_value(
            motor_id,
            model_info,
            position,
            DynamixelRegisters.GOAL_POSITION[0],
            DynamixelRegisters.GOAL_POSITION[1],
            "position",
        )
        if not ok:
            return False
        if velocity is not None:
            self.write_value(
                motor_id,
                model_info,
                velocity,
                DynamixelRegisters.GOAL_VELOCITY[0],
                DynamixelRegisters.GOAL_VELOCITY[1],
                "velocity",
            )
        return True

    def bulk_read_position(self, motors: dict[int, MotorModelInfo]) -> dict[int, float | None]:
        """Bulk-read positions and return radians per motor using `bulk_read_values`."""
        return self.bulk_read_values(
            motors, DynamixelRegisters.PRESENT_POSITION[0], DynamixelRegisters.PRESENT_POSITION[1], "position"
        )

    def bulk_write_position(
        self,
        positions: dict[int, float],
        motor_info: dict[int, MotorModelInfo],
        velocities: dict[int, float] | None = None,
    ) -> dict[int, bool]:
        """Bulk-write positions given in radians using provided `motor_info` for conversion.

        If `velocities` is provided, attempt to write velocity and position together
        in one GroupSyncWrite transaction for efficiency when supported.
        """
        # Bulk-write positions first. If velocities provided, filter to only those
        # motors whose position write succeeded and then bulk-write velocities for
        # that subset. Merge the results so velocity writes do not overwrite
        # position failures and only mark a motor successful if both (requested)
        # operations succeeded.
        results_pos = self.bulk_write_values(
            positions,
            motor_info,
            DynamixelRegisters.GOAL_POSITION[0],
            DynamixelRegisters.GOAL_POSITION[1],
            "position",
        )

        # Start with position results
        combined: dict[int, bool] = {mid: bool(ok) for mid, ok in results_pos.items()}

        if velocities:
            # Only attempt velocity writes for motors where position write succeeded
            vel_subset = {mid: v for mid, v in velocities.items() if results_pos.get(mid)}
            if vel_subset:
                results_vel = self.bulk_write_velocity(vel_subset, motor_info)
                for mid, pos_ok in results_pos.items():
                    if not pos_ok:
                        combined[mid] = False
                    else:
                        vel_ok = results_vel.get(mid, True)
                        combined[mid] = pos_ok and vel_ok

        return combined

    def read_velocity(self, motor_id: int, model_info: MotorModelInfo) -> float | None:
        """Read motor velocity in rad/s using `read_value`."""
        return self.read_value(
            motor_id,
            model_info,
            DynamixelRegisters.PRESENT_VELOCITY[0],
            DynamixelRegisters.PRESENT_VELOCITY[1],
            "velocity",
            signed=True,
        )

    def write_velocity(self, motor_id: int, model_info: MotorModelInfo, velocity: float) -> bool:
        """Write target velocity in rad/s using `write_value`.

        Exceptions from the underlying write propagate to the caller.
        """
        return self.write_value(
            motor_id,
            model_info,
            velocity,
            DynamixelRegisters.GOAL_VELOCITY[0],
            DynamixelRegisters.GOAL_VELOCITY[1],
            "velocity",
        )

    def bulk_read_velocity(self, motors: dict[int, MotorModelInfo]) -> dict[int, float | None]:
        """Bulk-read velocities (rad/s) via `bulk_read_values` with signed conversion."""
        return self.bulk_read_values(
            motors,
            DynamixelRegisters.PRESENT_VELOCITY[0],
            DynamixelRegisters.PRESENT_VELOCITY[1],
            "velocity",
            signed=True,
        )

    def bulk_write_velocity(
        self, velocities: dict[int, float], motor_info: dict[int, MotorModelInfo]
    ) -> dict[int, bool]:
        """Bulk-write velocities (rad/s) using provided `motor_info` for conversion."""
        if not motor_info:
            return {mid: False for mid in velocities.keys()}
        return self.bulk_write_values(
            velocities, motor_info, DynamixelRegisters.GOAL_VELOCITY[0], DynamixelRegisters.GOAL_VELOCITY[1], "velocity"
        )

    def read_current(self, motor_id: int, model_info: MotorModelInfo) -> float | None:
        """Read motor current in mA using `read_value`."""
        return self.read_value(
            motor_id,
            model_info,
            DynamixelRegisters.PRESENT_CURRENT[0],
            DynamixelRegisters.PRESENT_CURRENT[1],
            "current",
            signed=True,
        )

    def write_current(self, motor_id: int, model_info: MotorModelInfo, current_ma: float) -> bool:
        """Write target current in mA using `write_value`.

        Exceptions from the underlying write propagate to the caller.
        """
        return self.write_value(
            motor_id,
            model_info,
            current_ma,
            DynamixelRegisters.GOAL_CURRENT[0],
            DynamixelRegisters.GOAL_CURRENT[1],
            "current",
        )

    def bulk_read_current(self, motors: dict[int, MotorModelInfo]) -> dict[int, float | None]:
        """Bulk-read currents (mA) via `bulk_read_values` with signed conversion."""
        return self.bulk_read_values(
            motors, DynamixelRegisters.PRESENT_CURRENT[0], DynamixelRegisters.PRESENT_CURRENT[1], "current", signed=True
        )

    def bulk_write_current(self, currents: dict[int, float], motor_info: dict[int, MotorModelInfo]) -> dict[int, bool]:
        """Bulk-write currents (mA) using provided `motor_info` for conversion."""
        if not motor_info:
            return {mid: False for mid in currents.keys()}
        return self.bulk_write_values(
            currents, motor_info, DynamixelRegisters.GOAL_CURRENT[0], DynamixelRegisters.GOAL_CURRENT[1], "current"
        )

    def read_voltage(self, motor_id: int, model_info: MotorModelInfo) -> float | None:
        """Read supply voltage in volts."""
        return self.read_value(
            motor_id,
            model_info,
            DynamixelRegisters.PRESENT_VOLTAGE[0],
            DynamixelRegisters.PRESENT_VOLTAGE[1],
            "voltage",
        )

    def bulk_read_voltage(self, motors: dict[int, MotorModelInfo]) -> dict[int, float | None]:
        """Bulk read voltages (V) using bulk_read_values."""
        return self.bulk_read_values(
            motors, DynamixelRegisters.PRESENT_VOLTAGE[0], DynamixelRegisters.PRESENT_VOLTAGE[1], "voltage"
        )

    def read_temperature(self, motor_id: int, model_info: MotorModelInfo) -> float | None:
        """Read temperature in °C."""
        return self.read_value(
            motor_id,
            model_info,
            DynamixelRegisters.PRESENT_TEMPERATURE[0],
            DynamixelRegisters.PRESENT_TEMPERATURE[1],
            "temperature",
        )

    def bulk_read_temperature(self, motors: dict[int, MotorModelInfo]) -> dict[int, float | None]:
        """Bulk read temperatures (°C) using bulk_read_values."""
        return self.bulk_read_values(
            motors, DynamixelRegisters.PRESENT_TEMPERATURE[0], DynamixelRegisters.PRESENT_TEMPERATURE[1], "temperature"
        )

    def read_goal_position(self, motor_id: int, model_info: MotorModelInfo) -> float | None:
        """Read goal position and return radians using `read_value`."""
        return self.read_value(
            motor_id, model_info, DynamixelRegisters.GOAL_POSITION[0], DynamixelRegisters.GOAL_POSITION[1], "position"
        )

    def bulk_read_goal_position(self, motors: dict[int, MotorModelInfo]) -> dict[int, float | None]:
        """Bulk read goal positions (radians) via ``bulk_read_values``."""
        return self.bulk_read_values(
            motors, DynamixelRegisters.GOAL_POSITION[0], DynamixelRegisters.GOAL_POSITION[1], "position"
        )

    def supported_models(self) -> list[MotorModelInfo]:
        """Return a list of supported MotorModelInfo derived from the typed tables."""
        from .tables import DYNAMIXEL_MODELS_LIST

        return list(DYNAMIXEL_MODELS_LIST)

    def write_register(self, motor_id: int, address: int, value: float) -> None:
        """Write a register value to the motor.

        Automatically determines register size and handles signed conversion.

        Args:
            motor_id: Motor ID
            address: Register address
            value: Value to write
        """
        # Get register length
        length = self._get_register_length(address)

        # Encode signed if needed
        int_value = int(value)
        if address in SIGNED_REGISTERS:
            n_bytes = SIGNED_REGISTERS[address]
            int_value = encode_twos_complement(int_value, n_bytes)

        try:
            if length == 1:
                dxl_comm_result, dxl_error = self.packet_handler.write1ByteTxRx(
                    self.port_handler, motor_id, address, int_value
                )
            elif length == 2:
                dxl_comm_result, dxl_error = self.packet_handler.write2ByteTxRx(
                    self.port_handler, motor_id, address, int_value
                )
            elif length == 4:
                dxl_comm_result, dxl_error = self.packet_handler.write4ByteTxRx(
                    self.port_handler, motor_id, address, int_value
                )
            else:
                raise ValueError(f"Unsupported register length: {length}")

            if dxl_comm_result != COMM_SUCCESS:
                raise OperationalError(
                    i18n_key="hardware.motor_device.write_failed",
                    retriable=True,
                    interface=self.interface,
                    motor_id=motor_id,
                    register=address,
                )
        except OperationalError:
            raise
        except Exception as e:
            logger.error(f"Error writing register {address} to motor {motor_id}: {e}")
            raise OperationalError(
                i18n_key="hardware.motor_device.write_failed",
                retriable=True,
                interface=self.interface,
                motor_id=motor_id,
                register=address,
            ) from e

    def _decode_signed_register(self, address: int, value: int | None) -> int | None:
        """Decode a register value as signed if needed.

        Returns None if value is None.
        """
        if value is None:
            return None
        if address in SIGNED_REGISTERS:
            n_bytes = SIGNED_REGISTERS[address]
            return decode_twos_complement(value, n_bytes)
        return value

    def set_position(self, motor_id: int, position: float, velocity: float | None = None) -> bool:
        """
        Set motor target position.

        **Deprecated**: This legacy method accepts raw encoder units and is scheduled
        for removal. Prefer ``write_position`` which accepts positions in standard
        SI units (radians) and performs model-based conversion.

        Args:
            motor_id: Motor ID
            position: Target position (raw encoder units, 0-4095)
            velocity: Optional movement velocity (raw velocity units)

        Returns:
            True if command sent successfully
        """
        # Clamp position to valid range
        position = max(0, min(4095, int(round(position))))

        # Write goal position (may raise OperationalError)
        success = self.write_register(
            motor_id, DynamixelRegisters.GOAL_POSITION[0], position, DynamixelRegisters.GOAL_POSITION[1]
        )

        # Write velocity if provided
        if success and velocity is not None:
            velocity_int = max(0, min(2047, int(round(velocity))))  # Clamp velocity to valid range
            success = self.write_register(
                motor_id, DynamixelRegisters.GOAL_VELOCITY[0], velocity_int, DynamixelRegisters.GOAL_VELOCITY[1]
            )

        return success

    def set_velocity(self, motor_id: int, velocity: int) -> bool:
        """
        Set motor target velocity in raw hardware units.

        Args:
            motor_id: Motor ID
            velocity: Target velocity in raw hardware units (int)

        Returns:
            True if command sent successfully
        """
        # Clamp velocity to valid range (Dynamixel XL430: -2048 to 2047)
        velocity = max(-2048, min(2047, velocity))
        return self.write_register(
            motor_id, DynamixelRegisters.GOAL_VELOCITY[0], velocity, DynamixelRegisters.GOAL_VELOCITY[1]
        )

    def set_current(self, motor_id: int, current: int) -> bool:
        """
        Set motor target current.

        Args:
            motor_id: Motor ID
            current: Target current (raw current units)

        Returns:
            True if command sent successfully
        """
        # Clamp current to valid range
        current = max(-2048, min(2047, current))
        return self.write_register(
            motor_id, DynamixelRegisters.GOAL_CURRENT[0], current, DynamixelRegisters.GOAL_CURRENT[1]
        )

    def set_torque(self, motor_id: int, enabled: bool) -> bool:
        """
        Enable or disable motor torque.

        Args:
            motor_id: Motor ID
            enabled: True to enable torque, False to disable

        Returns:
            True if command sent successfully
        """
        value = 1 if enabled else 0
        return self.write_register(
            motor_id, DynamixelRegisters.TORQUE_ENABLE[0], value, DynamixelRegisters.TORQUE_ENABLE[1]
        )

    # ------------------------------------------------------------------
    # Homing and range (calibration) helpers
    # ------------------------------------------------------------------

    def supports_homing_offset(self, motor_id: int, model_info: MotorModelInfo) -> bool:
        """Return True if the motor model supports a homing offset register."""
        return dynamixel_supports_register(model_info.model, DynamixelRegisters.HOMING_OFFSET[0])

    def read_homing_offset(self, motor_id: int, model_info: MotorModelInfo) -> float:
        """Read homing offset from motor in protocol units. If unsupported, return 0.0 as fallback.

        Args:
            motor_id: Motor ID
            model_info: MotorModelInfo

        Returns:
            homing offset (raw protocol units) as float or 0.0 when unsupported
        """
        if not dynamixel_supports_register(model_info.model, DynamixelRegisters.HOMING_OFFSET[0]):
            return 0.0
        val = self._read_4byte(motor_id, DynamixelRegisters.HOMING_OFFSET[0])
        return float(val) if val is not None else 0.0

    def write_homing_offset(self, motor_id: int, model_info: MotorModelInfo, offset: float | None = None) -> bool:
        """Write homing offset to motor in protocol units.

        If `offset` is None, the driver's current position is read and written as the
        homing offset. Drivers do NOT swallow exceptions — communication errors
        or unexpected failures will raise.

        Returns True on successful write, False when motor does not support the register.
        """
        if not dynamixel_supports_register(model_info.model, DynamixelRegisters.HOMING_OFFSET[0]):
            return False

        # If offset not provided, use current position from the motor
        if offset is None:
            pos = self._read_position(motor_id, model_info)
            if pos is None:
                raise ValueError(f"Cannot determine current position for homing offset on motor {motor_id}")
            offset = float(pos)

        # Convert float protocol units to integer register value and write (may raise OperationalError)
        offset_int = int(round(offset))
        return self.write_register(
            motor_id, DynamixelRegisters.HOMING_OFFSET[0], offset_int, DynamixelRegisters.HOMING_OFFSET[1]
        )

    def read_range(self, motor_id: int, model_info: MotorModelInfo) -> tuple[float, float]:
        """Read range_min and range_max from motor in protocol units. If unsupported, return (0.0, max_res - 1).

        Uses `model_info.encoder_resolution` if available; otherwise defaults to 4096.
        """
        default_res = model_info.encoder_resolution
        fallback = (0.0, float(int(default_res - 1)))

        if not (
            dynamixel_supports_register(model_info.model, DynamixelRegisters.RANGE_MIN[0])
            and dynamixel_supports_register(model_info.model, DynamixelRegisters.RANGE_MAX[0])
        ):
            return fallback

        try:
            rmin = self._read_4byte(motor_id, DynamixelRegisters.RANGE_MIN[0])
            rmax = self._read_4byte(motor_id, DynamixelRegisters.RANGE_MAX[0])
            return (float(rmin), float(rmax))
        except Exception as e:
            logger.warning(f"Failed to read range for motor {motor_id}: {e}")
            return fallback

    def write_range(self, motor_id: int, model_info: MotorModelInfo, range_min: float, range_max: float) -> bool:
        """Write range limits to motor in protocol units. Returns False if unsupported or failed."""
        if not (
            dynamixel_supports_register(model_info.model, DynamixelRegisters.RANGE_MIN[0])
            and dynamixel_supports_register(model_info.model, DynamixelRegisters.RANGE_MAX[0])
        ):
            return False

        try:
            ok1 = self.write_register(
                motor_id, DynamixelRegisters.RANGE_MIN[0], int(round(range_min)), DynamixelRegisters.RANGE_MIN[1]
            )
            ok2 = self.write_register(
                motor_id, DynamixelRegisters.RANGE_MAX[0], int(round(range_max)), DynamixelRegisters.RANGE_MAX[1]
            )
            return ok1 and ok2
        except Exception as e:
            logger.error(f"Failed to write range for motor {motor_id}: {e}")
            return False

    def bulk_set_torque(self, motor_ids: list[int], enabled: bool) -> dict[int, bool]:
        """Set torque for multiple motors at once using sync write.

        Uses Dynamixel's GroupSyncWrite for efficient single-transaction bulk writes.

        Args:
            motor_ids: List of motor IDs
            enabled: True to enable, False to disable

        Returns:
            Dict mapping motor_id -> success (bool)
        """
        if not self.group_sync_write:
            # Fallback to individual writes
            return {motor_id: self.set_torque(motor_id, enabled) for motor_id in motor_ids}

        # Ensure connection before using group sync write
        self._ensure_connected()

        # Reinitialize GroupSyncWrite for this specific register (Torque Enable)
        self.group_sync_write = GroupSyncWrite(
            self.port_handler,
            self.packet_handler,
            DynamixelRegisters.TORQUE_ENABLE[0],
            DynamixelRegisters.TORQUE_ENABLE[1],
        )

        value = 1 if enabled else 0
        value_bytes = [value]

        # Add parameters for sync write
        for motor_id in motor_ids:
            if not self.group_sync_write.addParam(motor_id, value_bytes):
                logger.warning(f"Failed to add torque param for motor {motor_id}")
                # If one fails to even add, we might want to continue or fallback
                # For consistency, we'll try to add all we can

        # Perform sync write (single bus transaction)
        dxl_comm_result = self.group_sync_write.txPacket()

        success = dxl_comm_result == COMM_SUCCESS
        if not success:
            logger.error(f"Sync write failed: {self.packet_handler.getTxRxResult(dxl_comm_result)}")

        self.group_sync_write.clearParam()
        # If sync write succeeds, all motors in the sync write are considered successful
        # (assuming hardware received it; sync write doesn't provide per-motor feedback)
        return {motor_id: success for motor_id in motor_ids}

    def bulk_set_position(self, positions: dict[int, float], velocity: float | None = None) -> dict[int, bool]:
        """Set target positions (and optionally speeds) for multiple motors efficiently.

        Performance Optimization:
        If `velocity` is provided, uses an 8-byte GroupSyncWrite starting from
        `Profile Velocity` (112) to set both Velocity and Position in a single
        bus transaction. This halves the latency compared to separate writes.

        Args:
            positions: Dict mapping motor_id -> target position (raw units, 0-4095)
            velocity: Optional movement velocity (applied to all motors, raw units)

        Returns:
            Dict mapping motor_id -> success (bool)
        """
        if not self.group_sync_write:
            # Fallback to individual writes
            return {motor_id: self.set_position(motor_id, pos, velocity) for motor_id, pos in positions.items()}

        # Ensure connection before using group sync write
        self._ensure_connected()

        # Decide register address and length based on whether velocity is provided
        if velocity is not None:
            # Optimized 8-byte write (Velocity @ 112, Position @ 116)
            start_addr = DynamixelRegisters.PROFILE_VELOCITY[0]
            data_len = DynamixelRegisters.PROFILE_VELOCITY[1] + DynamixelRegisters.GOAL_POSITION[1]
        else:
            # standard 4-byte write (Position @ 116)
            start_addr = DynamixelRegisters.GOAL_POSITION[0]
            data_len = DynamixelRegisters.GOAL_POSITION[1]

        self.group_sync_write = GroupSyncWrite(
            self.port_handler,
            self.packet_handler,
            start_addr,
            data_len,
        )

        # Add parameters for each motor
        for motor_id, position in positions.items():
            # Clamp position
            position = max(0, min(4095, int(position)))

            if velocity is not None:
                # 8 bytes: [Velocity (4), Position (4)]
                v = int(velocity)
                p = position
                payload = [
                    v & 0xFF,
                    (v >> 8) & 0xFF,
                    (v >> 16) & 0xFF,
                    (v >> 24) & 0xFF,
                    p & 0xFF,
                    (p >> 8) & 0xFF,
                    (p >> 16) & 0xFF,
                    (p >> 24) & 0xFF,
                ]
            else:
                # 4 bytes: [Position (4)]
                p = position
                payload = [p & 0xFF, (p >> 8) & 0xFF, (p >> 16) & 0xFF, (p >> 24) & 0xFF]

            if not self.group_sync_write.addParam(motor_id, payload):
                logger.warning(f"Failed to add position param for motor {motor_id}")

        # Perform sync write (single bus transaction)
        dxl_comm_result = self.group_sync_write.txPacket()
        success = dxl_comm_result == COMM_SUCCESS
        if not success:
            logger.error(f"Sync write failed: {self.packet_handler.getTxRxResult(dxl_comm_result)}")

        self.group_sync_write.clearParam()
        return {motor_id: success for motor_id in positions.keys()}

    def bulk_write_register(
        self,
        motor_values: dict[int, int],
        register_addr: int,
        register_len: int,
    ) -> dict[int, bool]:
        """Write the same register to multiple motors using GroupSyncWrite.

        Optimized for batch initialization (operating mode, current limits, etc.).
        Supports both signed and unsigned values - negative values are automatically
        encoded using two's complement.

        Args:
            motor_values: Dict mapping motor_id -> value to write (supports negative values)
            register_addr: Register address to write
            register_len: Register length in bytes (1, 2, or 4)

        Returns:
            Dict mapping motor_id -> success (bool)

        Example:
            # Supports negative values (e.g., velocity limits)
            driver.bulk_write_register(
                {1: -100, 2: 100, 3: -50},  # Negative values OK
                register_addr=112,
                register_len=4
            )
        """
        if not self.group_sync_write or not motor_values:
            # Fallback to individual writes
            return {
                mid: self.write_register(mid, register_addr, val, register_len) for mid, val in motor_values.items()
            }

        self._ensure_connected()

        # Initialize GroupSyncWrite for this register
        self.group_sync_write = GroupSyncWrite(
            self.port_handler,
            self.packet_handler,
            register_addr,
            register_len,
        )

        # Add parameters for each motor
        for motor_id, value in motor_values.items():
            # Convert to unsigned using two's complement for negative values
            payload = self._encode_register_value(value, register_len)
            if payload is None:
                logger.error(f"Unsupported register length: {register_len}")
                return {mid: False for mid in motor_values.keys()}

            if not self.group_sync_write.addParam(motor_id, payload):
                logger.warning(f"Failed to add param for motor {motor_id}")

        # Perform sync write
        dxl_comm_result = self.group_sync_write.txPacket()
        success = dxl_comm_result == COMM_SUCCESS
        if not success:
            logger.error(f"Bulk write register failed: {self.packet_handler.getTxRxResult(dxl_comm_result)}")

        self.group_sync_write.clearParam()
        return {motor_id: success for motor_id in motor_values.keys()}

    # ========== High-level API: Physical Units ==========
    # These methods accept physical units (mA, rad/s, etc.) and convert internally

    def bulk_write_current_limit(
        self,
        motor_currents: dict[int, float],
        current_unit_ma: float | None = None,
    ) -> dict[int, bool]:
        """Set current limit for multiple motors (high-level API).

        Args:
            motor_currents: Dict mapping motor_id -> current limit in mA
            current_unit_ma: Optional custom unit (default: 2.69mA/unit for X-series)

        Returns:
            Dict mapping motor_id -> success (bool)

        Example:
            # Set 1000mA limit for motors 1, 2, 3
            driver.bulk_write_current_limit({1: 1000, 2: 1000, 3: 800})
        """
        from .tables import DynamixelRegisters, DynamixelUnits

        unit = current_unit_ma or DynamixelUnits.CURRENT_MA_PER_UNIT
        register_values = {mid: int(current_ma / unit) for mid, current_ma in motor_currents.items()}

        return self.bulk_write_register(
            register_values,
            DynamixelRegisters.CURRENT_LIMIT[0],
            DynamixelRegisters.CURRENT_LIMIT[1],
        )

    def bulk_write_velocity_limit(
        self,
        motor_velocities: dict[int, float],
        velocity_unit_rad_s: float | None = None,
    ) -> dict[int, bool]:
        """Set velocity limit for multiple motors (high-level API).

        Args:
            motor_velocities: Dict mapping motor_id -> velocity limit in rad/s
            velocity_unit_rad_s: Optional custom unit (default: 0.02398 rad/s/unit)

        Returns:
            Dict mapping motor_id -> success (bool)

        Example:
            # Set 2.0 rad/s limit for motors
            driver.bulk_write_velocity_limit({1: 2.0, 2: 1.5, 3: 2.5})
        """
        from .tables import DynamixelRegisters, DynamixelUnits

        unit = velocity_unit_rad_s or DynamixelUnits.VELOCITY_RAD_S_PER_UNIT
        register_values = {mid: int(vel_rad_s / unit) for mid, vel_rad_s in motor_velocities.items()}

        return self.bulk_write_register(
            register_values,
            DynamixelRegisters.VELOCITY_LIMIT[0],
            DynamixelRegisters.VELOCITY_LIMIT[1],
        )

    def bulk_write_temperature_limit(
        self,
        motor_temperatures: dict[int, float],
    ) -> dict[int, bool]:
        """Set temperature limit for multiple motors (high-level API).

        Args:
            motor_temperatures: Dict mapping motor_id -> temperature limit in °C

        Returns:
            Dict mapping motor_id -> success (bool)

        Example:
            # Set 70°C limit
            driver.bulk_write_temperature_limit({1: 70, 2: 70, 3: 65})
        """
        from .tables import DynamixelRegisters, DynamixelUnits

        # Temperature has 1:1 mapping
        register_values = {
            mid: int(temp_c / DynamixelUnits.TEMPERATURE_C_PER_UNIT) for mid, temp_c in motor_temperatures.items()
        }

        return self.bulk_write_register(
            register_values,
            DynamixelRegisters.TEMPERATURE_LIMIT[0],
            DynamixelRegisters.TEMPERATURE_LIMIT[1],
        )

    def bulk_write_operating_mode(
        self,
        motor_modes: dict[int, int],
    ) -> dict[int, bool]:
        """Set operating mode for multiple motors (high-level API).

        Args:
            motor_modes: Dict mapping motor_id -> operating mode
                         0: Current Control
                         1: Velocity Control
                         3: Position Control (default)
                         4: Extended Position Control
                         5: Current-based Position Control
                         16: PWM Control

        Returns:
            Dict mapping motor_id -> success (bool)

        Example:
            # Set position control mode
            driver.bulk_write_operating_mode({1: 3, 2: 3, 3: 3})
        """
        from .tables import DynamixelRegisters

        return self.bulk_write_register(
            motor_modes,
            DynamixelRegisters.OPERATING_MODE[0],
            DynamixelRegisters.OPERATING_MODE[1],
        )

    def bulk_write_drive_mode(
        self,
        motor_drive_modes: dict[int, int],
    ) -> dict[int, bool]:
        """Set drive mode for multiple motors (high-level API).

        Args:
            motor_drive_modes: Dict mapping motor_id -> drive mode
                              Bit 0: Reverse mode (0=Normal, 1=Reverse)
                              Bit 2: Profile configuration (0=Velocity-based, 1=Time-based)

        Returns:
            Dict mapping motor_id -> success (bool)

        Example:
            # Set motors 2,4 to reverse mode
            driver.bulk_write_drive_mode({1: 0, 2: 1, 3: 0, 4: 1})
        """
        from .tables import DynamixelRegisters

        return self.bulk_write_register(
            motor_drive_modes,
            DynamixelRegisters.DRIVE_MODE[0],
            DynamixelRegisters.DRIVE_MODE[1],
        )

    def _encode_register_value(self, value: int, length: int) -> list[int] | None:
        """Encode a signed or unsigned integer value as little-endian bytes.

        Handles two's complement encoding for negative values automatically.

        Args:
            value: Integer value (can be negative)
            length: Register length in bytes (1, 2, or 4)

        Returns:
            List of bytes (little-endian) or None if length invalid
        """
        # Convert to unsigned using two's complement for negative values
        if length == 1:
            unsigned = value & 0xFF
            return [unsigned]
        elif length == 2:
            unsigned = value & 0xFFFF
            return [unsigned & 0xFF, (unsigned >> 8) & 0xFF]
        elif length == 4:
            unsigned = value & 0xFFFFFFFF
            return [
                unsigned & 0xFF,
                (unsigned >> 8) & 0xFF,
                (unsigned >> 16) & 0xFF,
                (unsigned >> 24) & 0xFF,
            ]
        else:
            return None

    def _convert_raw_telemetry(
        self,
        position: int,
        velocity: int,
        current: int,
        voltage: int,
        temperature: int,
        goal_position: int,
        model_info: MotorModelInfo | None = None,
    ) -> tuple[int, int, float | None, float | None, float | None, int | None, bool, int]:
        """Normalize raw register values for MotorTelemetry.

        Important: Drivers MUST return values in *hardware raw units* where possible:
        - position and goal_position: raw encoder counts (int)
        - velocity: raw hardware velocity units (int)
        - current: converted to mA (float) when available
        - voltage: converted to V (float) when available
        - temperature: Celsius (float) when available

        Unit conversions to rad/rad/s are performed by MotorBus using model_info
        (position_to_radian_ratio/velocity_ratio). This keeps driver outputs
        consistent and avoids double-conversion when MotorBus handles position_type
        conversions.
        """
        # Return raw encoder counts for position and goal_position (int)
        pos_raw = int(position) if position is not None else 0
        goal_raw = int(goal_position) if goal_position is not None else pos_raw

        # Velocity: signed raw hardware units (32-bit register)
        vel_signed = self._decode_signed_register(DynamixelRegisters.PRESENT_VELOCITY[0], velocity)
        velocity_raw = int(vel_signed) if vel_signed is not None else 0

        # Current: convert 16-bit signed to mA (unit depends on model; typically 1 mA per unit)
        cur_signed = self._decode_signed_register(DynamixelRegisters.PRESENT_CURRENT[0], current)
        current_ma: float | None = None if cur_signed is None else float(cur_signed)

        # Voltage: raw value to V (unit: 0.1V per unit)
        voltage_v: float | None = None if voltage is None else float(voltage) / 10.0

        # Temperature: return as float if present
        temp_c: float | None = float(temperature) if temperature is not None else None

        # Determine if motor is moving (velocity != 0)
        moving = abs(velocity_raw) > 0

        # Load: unavailable reliably -> None
        load: int | None = None

        return pos_raw, velocity_raw, current_ma, voltage_v, temp_c, load, moving, goal_raw

    def read_telemetry(self, motor_id: int, model_info: MotorModelInfo) -> MotorTelemetry | None:
        """
        Read real-time telemetry from a single motor.

        Args:
            motor_id: Motor ID
            model_info: `MotorModelInfo` (required)

        Returns:
            Motor telemetry data or None if critical read fails
        """
        # Read present position (critical - return None if unsupported or failed)
        position = self._read_position(motor_id, model_info)
        if position is None:
            logger.error(f"Position not supported or failed to read for motor {motor_id}")
            return None

        # Normalize position to valid range (handle Extended Position Mode)
        resolution = int(model_info.encoder_resolution)
        if position >= resolution:
            normalized_pos = position % resolution
            logger.debug(
                f"Motor {motor_id}: position {position} normalized to {normalized_pos} (resolution={resolution})"
            )
            position = normalized_pos

        # Read other telemetry data (methods handle support checks internally)
        velocity = self._read_velocity(motor_id, model_info) or 0
        current = self._read_current(motor_id, model_info)
        voltage = self._read_voltage(motor_id, model_info)
        temperature = self._read_temperature(motor_id, model_info)
        goal_position = self._read_goal_position(motor_id, model_info) or position

        # Normalize goal_position too
        if goal_position >= resolution:
            goal_position = goal_position % resolution

        # Normalize raw values (keep in hardware units; MotorBus will convert to rad/rad/s as needed)
        (
            pos_raw,
            velocity_raw,
            current_ma,
            voltage_v,
            temp,
            load,
            moving,
            goal_raw,
        ) = self._convert_raw_telemetry(position, velocity, current, voltage, temperature, goal_position, model_info)

        return MotorTelemetry(
            id=motor_id,
            position=float(pos_raw) if pos_raw is not None else None,
            position_type=PositionType.RAW,
            goal_position=float(goal_raw) if goal_raw is not None else None,
            velocity=velocity_raw,
            current=current_ma,
            load=load,
            temperature=temp,
            voltage=voltage_v,
            moving=moving,
            error=0,
        )

    # _setup_sync_reader removed — inline per-register GroupSyncRead logic is used directly
    # in `bulk_read_telemetry`. See commit history for previous implementation if needed.

    # _extract_telemetry_from_sync removed — extraction logic has been inlined into
    # `bulk_read_telemetry` to simplify flow and enable integrated validation/fallbacks.
    def _fallback_individual_reads(self, motors: dict[int, MotorModelInfo]) -> dict[int, MotorTelemetry]:
        """Fallback to individual telemetry reads when bulk read fails."""
        result = {}
        for motor_id, motor_info in motors.items():
            telemetry = self.read_telemetry(motor_id, motor_info)
            if telemetry:
                result[motor_id] = telemetry
        return result

    def bulk_read_telemetry(self, motors: dict[int, MotorModelInfo]) -> dict[int, MotorTelemetry]:
        """
        Read telemetry from multiple motors efficiently using sync read.

        Uses per-register GroupSyncRead approach compatible with dynamixel-sdk.
        Each register is read in a separate sync read transaction.

        Args:
            motors: Mapping of motor_id -> MotorModelInfo

        Returns:
            Dict mapping motor_id -> telemetry
        """
        if not self.group_sync_read or not motors:
            return self._fallback_individual_reads(motors)

        self._ensure_connected()

        try:
            # Registers to read for telemetry
            registers = [
                DynamixelRegisters.PRESENT_POSITION,
                DynamixelRegisters.PRESENT_VELOCITY,
                DynamixelRegisters.PRESENT_CURRENT,
                DynamixelRegisters.PRESENT_VOLTAGE,
                DynamixelRegisters.PRESENT_TEMPERATURE,
                DynamixelRegisters.GOAL_POSITION,
            ]

            # Accumulate raw values per motor
            raw_vals: dict[int, dict[str, int | None]] = {
                motor_id: {
                    "position": None,
                    "velocity": None,
                    "current": None,
                    "voltage": None,
                    "temperature": None,
                    "goal_position": None,
                }
                for motor_id in motors.keys()
            }

            # Read each register using GroupSyncRead
            for addr, length in registers:
                # Create new GroupSyncRead for this register (per lerobot approach)
                sync_reader = GroupSyncRead(self.port_handler, self.packet_handler, addr, length)

                try:
                    # Add motors that support this register
                    motors_to_read = []
                    for motor_id, model_info in motors.items():
                        if dynamixel_supports_register(model_info.model, addr):
                            if sync_reader.addParam(motor_id):
                                motors_to_read.append(motor_id)
                            else:
                                logger.debug(f"Failed to add motor {motor_id} to sync read for addr {addr}")

                    if not motors_to_read:
                        continue

                    # Execute sync read
                    dxl_comm_result = sync_reader.txRxPacket()
                    if dxl_comm_result != COMM_SUCCESS:
                        logger.warning(
                            f"Sync read failed for addr {addr}: {self.packet_handler.getTxRxResult(dxl_comm_result)}"
                        )
                        sync_reader.clearParam()
                        continue

                    # Extract data for each motor
                    for motor_id in motors_to_read:
                        if not sync_reader.isAvailable(motor_id, addr, length):
                            logger.debug(f"Data not available for motor {motor_id} addr {addr}")
                            continue

                        val = sync_reader.getData(motor_id, addr, length)

                        # Store in accumulator based on register
                        if addr == DynamixelRegisters.PRESENT_POSITION[0]:
                            raw_vals[motor_id]["position"] = val
                        elif addr == DynamixelRegisters.PRESENT_VELOCITY[0]:
                            raw_vals[motor_id]["velocity"] = val
                        elif addr == DynamixelRegisters.PRESENT_CURRENT[0]:
                            raw_vals[motor_id]["current"] = val
                        elif addr == DynamixelRegisters.PRESENT_VOLTAGE[0]:
                            raw_vals[motor_id]["voltage"] = val
                        elif addr == DynamixelRegisters.PRESENT_TEMPERATURE[0]:
                            raw_vals[motor_id]["temperature"] = val
                        elif addr == DynamixelRegisters.GOAL_POSITION[0]:
                            raw_vals[motor_id]["goal_position"] = val

                finally:
                    sync_reader.clearParam()

            # Build telemetry from accumulated values
            result: dict[int, MotorTelemetry] = {}
            for motor_id, model_info in motors.items():
                pos = raw_vals[motor_id]["position"]

                if pos is None:
                    # Position is critical - fallback to individual read
                    telemetry = self.read_telemetry(motor_id, model_info)
                    if telemetry:
                        result[motor_id] = telemetry
                    continue

                # Normalize position value
                # Note: Position register returns unsigned 32-bit value.
                # In Extended Position Control Mode (mode 4), values can exceed encoder_resolution
                # and represent multi-turn positions. We normalize to single-turn range via modulo.
                pos = int(pos) & 0xFFFFFFFF  # Ensure 32-bit unsigned

                resolution = int(model_info.encoder_resolution)
                if pos >= resolution:
                    # Normalize to single-turn range (0 to resolution-1)
                    # This handles both Extended Position Mode and out-of-range values
                    normalized_pos = pos % resolution
                    logger.debug(
                        f"Motor {motor_id}: position {pos} exceeds resolution {resolution}, "
                        f"normalized to {normalized_pos} (likely Extended Position Mode)"
                    )
                    pos = normalized_pos

                velocity = raw_vals[motor_id]["velocity"] or 0
                current = raw_vals[motor_id]["current"]
                voltage = raw_vals[motor_id]["voltage"]
                temperature = raw_vals[motor_id]["temperature"]
                goal_position = (
                    raw_vals[motor_id]["goal_position"] if raw_vals[motor_id]["goal_position"] is not None else pos
                )

                (
                    pos_raw,
                    velocity_raw,
                    current_ma,
                    voltage_v,
                    temp,
                    load,
                    moving,
                    goal_raw,
                ) = self._convert_raw_telemetry(pos, velocity, current, voltage, temperature, goal_position, model_info)

                result[motor_id] = MotorTelemetry(
                    id=motor_id,
                    position=float(pos_raw) if pos_raw is not None else None,
                    position_type=PositionType.RAW,
                    goal_position=float(goal_raw) if goal_raw is not None else None,
                    velocity=velocity_raw,
                    current=current_ma,
                    load=load,
                    temperature=temp,
                    voltage=voltage_v,
                    moving=moving,
                    error=0,
                )

            return result

        except Exception as e:
            logger.error(f"Bulk telemetry read failed: {e}", exc_info=True)
            return self._fallback_individual_reads(motors)
