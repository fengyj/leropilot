"""
Abstract base driver for motor bus communication.

All motor drivers inherit from this base class and implement protocol-specific logic.
"""

import time
from abc import ABC, abstractmethod
from threading import RLock
from typing import Generic, Literal, TypeVar

from typing_extensions import Self

from leropilot.models.hardware import MotorBrand, MotorModelInfo, MotorTelemetry, UnitType

# Generic motor id type for drivers
MotorIDVar = TypeVar("MotorIDVar")


class BaseMotorDriver(ABC, Generic[MotorIDVar]):
    """Abstract base class for motor bus drivers.

    Standard Physical Units:
        All motor drivers use the following standard units for physical values:

        - Position: radians (rad)
        - Velocity: radians per second (rad/s)
        - Acceleration: radians per second squared (rad/s²)
        - Current: milliamperes (mA)
        - Voltage: volts (V)
        - Temperature: degrees Celsius (°C)
        - Torque: Newton-meters (N·m)
        - Force: Newtons (N)
        - Time: seconds (s)

        Methods ending with '_values' (e.g., bulk_write_values, bulk_read_values)
        accept/return these standard units.

        Methods ending with '_register' (e.g., bulk_write_register, bulk_read_register)
        accept/return raw integer register values (driver-specific encoding).

    Thread Safety:
        This class and its subclasses are NOT thread-safe by design.
        All methods assume single-threaded access or external synchronization.

        If you need concurrent access from multiple threads (e.g., separate
        control and monitoring threads), you must:
        1. Use external locking (e.g., threading.RLock) around all driver calls, OR
        2. Create separate driver instances per thread (not recommended for
           shared resources like serial ports or CAN buses)

        Rationale: Adding internal locks would impose performance overhead for
        the common single-threaded use case (typical control loops).
    """

    def __init__(self, interface: str, baud_rate: int | None = None) -> None:
        """
        Initialize driver.

        Args:
            interface: Communication interface (e.g., "COM11", "can0")
            baud_rate: Baud rate (serial) or bit rate (CAN)
        """
        self.interface = interface
        self.baud_rate = baud_rate
        self.connected = False
        # Note: drivers should be stateless with respect to assigned motor ids.
        # MotorBus is responsible for mapping motor_id -> driver; avoid storing
        # assigned motor id on driver instances to reduce coupling.

    @abstractmethod
    def connect(self) -> None:
        """
        Connect to the motor bus.

        Should raise :class:`OperationalError` on failure instead of returning False.
        """
        pass

    @abstractmethod
    def disconnect(self) -> bool:
        """
        Disconnect from the motor bus.

        Returns:
            True if disconnection successful
        """
        pass

    def is_connected(self) -> bool:
        """Check if driver is connected"""
        return self.connected

    def __enter__(self) -> Self:
        """Context manager support"""
        self.connect()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object | None,
    ) -> Literal[False]:
        """Context manager cleanup"""
        self.disconnect()
        return False

    @abstractmethod
    def scan_motors(self, scan_range: list[int] | None = None) -> dict[MotorIDVar, MotorModelInfo]:
        """
        Scan motor bus and discover all motors.

        Args:
            scan_range: List of motor IDs to scan (default: 1-253)

        Returns:
            Mapping of motor id -> MotorModelInfo for discovered motors
        """
        pass

    @abstractmethod
    def identify_model(
        self,
        motor_id: MotorIDVar,
        model_number: int | None = None,
        fw_major: int | None = None,
        fw_minor: int | None = None,
        raise_on_ambiguous: bool = False,
    ) -> MotorModelInfo:
        """
        Identify the model and variant of a motor. Callers may provide pre-read
        `model_number`, `fw_major`, and `fw_minor` to avoid extra register reads
        (useful during bus scans).

        Returns:
            `MotorModelInfo` on success.

        Raises:
            ValueError: if the model cannot be identified.
            RuntimeError: if the driver is not ready to perform identification.
        """
        pass

    @abstractmethod
    def supported_models(self) -> list[MotorModelInfo]:
        """
        Return a list of `MotorModelInfo` instances representing the motor models
        and variants that this driver can identify/handle.
        """
        pass

    @abstractmethod
    def read_register(self, motor_id: MotorIDVar, address: int) -> float:
        """
        Read a register value from a motor.
        How many bytes are read depends on the register. And the sign of the value is also
        determined by the register type. The implementation should handle these details.

        Args:
            motor_id: Motor ID
            address: Register address

        Returns:
            Raw register value (int or float depending on register type, int value will convert to float)
        """
        pass

    @abstractmethod
    def write_register(self, motor_id: MotorIDVar, address: int, value: float) -> None:
        """Write a register value to a motor.

        Args:
            motor_id: Motor ID
            address: Register address
            value: Value to write
        """
        pass

    def bulk_read_registers(
        self,
        motor_ids: list[MotorIDVar],
        register_addr: int,
    ) -> dict[MotorIDVar, float]:
        """Read the same register from multiple motors (raw register values).

        Default implementation uses sequential reads. Subclasses should override
        for protocol-specific bulk read optimization.

        Args:
            motor_ids: List of motor IDs to read from
            register_addr: Register address to read

        Returns:
            Dict mapping motor_id -> raw register value

        Example:
            # Read current limits (raw register values)
            currents = driver.bulk_read_registers([1, 2, 3], addr=38)
            # Returns: {1: 372.0, 2: 297.0}
        """
        results: dict[MotorIDVar, float] = {}
        for motor_id in motor_ids:
            value = self.read_register(motor_id, register_addr)
            results[motor_id] = value
            time.sleep(0.001)  # Small delay to avoid bus overload
        return results

    def bulk_write_registers(
        self,
        motor_values: dict[MotorIDVar, float],
        register_addr: int,
    ) -> None:
        """Write the same register to multiple motors with different values.

        This is useful for batch initialization, e.g., setting operating mode,
        drive mode, current limits, etc. for multiple motors.

        Supports both signed and unsigned integer values. Negative values are
        automatically encoded using two's complement representation.

        Args:
            motor_values: Dict mapping motor_id -> raw register value (can be negative)
            register_addr: Register address to write

        Example:
            # Set velocity limit (supports negative values)
            driver.bulk_write_register(
                {1: -100, 2: 100, 3: -50},  # Negative values OK
                register_addr=112,  # Profile Velocity register
            )
        """
        # Default implementation: sequential writes
        # Subclasses should override for protocol-specific bulk write
        for motor_id, value in motor_values.items():
            # Each driver should implement `write_register` method
            self.write_register(motor_id, register_addr, value)
            time.sleep(0.001)  # Small delay to avoid bus overload

    def read_register_in_standard_unit(
        self,
        motor_id: MotorIDVar,
        model_info: MotorModelInfo,
        address: int,
        unit_type: UnitType,
    ) -> float:
        """Read a physical value from a motor register.

        Reads a raw register value via `read_register`, then converts it into
        standard physical units (e.g., mA for current, rad/s for velocity)
        using the motor's `MotorModelInfo`.

        Args:
            motor_id: Motor ID
            address: Register address
            unit_type: Type of physical unit ("current", "velocity", "acceleration",
                      "temperature", "voltage")
            model_info: Optional `MotorModelInfo` for the motor. If not provided
                        the driver must override this method to supply lookup.
        Returns:
            Value in STANDARD UNITS (e.g., mA for current, rad/s for velocity)
            or None if read failed
        """

        # Read raw register value
        raw_value = self.read_register(motor_id, address)
        # Get conversion factor and compute physical value (will raise if missing)

        physical_value = model_info.convert_to_standard_unit(unit_type, raw_value)
        return physical_value

    def write_register_in_standard_unit(
        self,
        motor_id: MotorIDVar,
        model_info: MotorModelInfo,
        address: int,
        value: float,
        unit_type: UnitType,
    ) -> None:
        """Write a physical value to a motor register.

        Converts a value expressed in standard physical units (e.g., mA for current,
        rad/s for velocity) into the appropriate raw register value using
        the motor's `MotorModelInfo`, then writes it via `write_register`.

        Args:
            motor_id: Motor ID
            model_info: Optional `MotorModelInfo` for the motor. If not provided
                        the driver must override this method to supply lookup.
            address: Register address
            value: Value in STANDARD UNITS (e.g., mA for current, rad/s for velocity)
            unit_type: Type of physical unit ("current", "velocity", "acceleration",
                      "temperature", "voltage")

        Raises:
            ValueError: If conversion factor not available for the motor model

        """
        # Drivers or callers should provide MotorModelInfo when possible to
        # perform unit conversions. Base cannot look it up generically.

        # Get conversion factor and compute raw register value (will raise if missing)
        register_value = model_info.convert_from_standard_unit(unit_type, value)

        # Delegate to write_register (driver-specific implementation)
        return self.write_register(motor_id, address, register_value)

    def bulk_read_registers_in_standard_unit(
        self,
        motor_models: dict[MotorIDVar, MotorModelInfo],
        register_addr: int,
        unit_type: UnitType,
    ) -> dict[MotorIDVar, float]:
        """Read register values in standard physical units from multiple motors.

        This method automatically looks up the appropriate conversion factor from
        each motor's MotorModelInfo based on the unit_type.

        Args:
            register_addr: Register address to read
            motor_models: Dict mapping motor_id -> MotorModelInfo (for conversion factors)
            unit_type: Type of physical unit ("current", "velocity", "acceleration",
                      "temperature", "voltage")

        Returns:
            Dict mapping motor_id -> value in STANDARD UNITS

        Raises:
            ValueError: If conversion factor not available for a motor model

        """
        # Read raw register values
        motor_ids = list(motor_models.keys())
        raw_values = self.bulk_read_registers(motor_ids, register_addr)

        # Convert to physical units
        results: dict[MotorIDVar, float] = {}
        for motor_id, raw_value in raw_values.items():
            model_info = motor_models[motor_id]
            # Convert to physical units
            results[motor_id] = model_info.convert_to_standard_unit(unit_type, raw_value)

        return results

    def bulk_write_registers_in_standard_unit(
        self,
        motor_values: dict[MotorIDVar, float],
        motor_models: dict[MotorIDVar, MotorModelInfo],
        register_addr: int,
        unit_type: UnitType,
    ) -> None:
        """Write values in standard physical units to multiple motors.

        This method automatically looks up the appropriate conversion factor from
        each motor's MotorModelInfo based on the unit_type.

        Args:
            register_addr: Register address to write
            motor_values: Dict mapping motor_id -> value in STANDARD UNITS
                         (e.g., mA for current, rad/s for velocity)
            motor_models: Dict mapping motor_id -> MotorModelInfo (for conversion factors)
            unit_type: Type of physical unit ("current", "velocity", "acceleration",
                      "temperature", "voltage")

        Raises:
            ValueError: If conversion factor not available for a motor model

        """
        # Convert physical units to raw register values
        register_values: dict[MotorIDVar, float] = {}

        for motor_id, physical_value in motor_values.items():
            # Caller is required to provide MotorModelInfo for each motor
            model_info = motor_models[motor_id]

            register_values[motor_id] = model_info.convert_from_standard_unit(unit_type, physical_value)

        self.bulk_write_registers(register_values, register_addr)

    @abstractmethod
    def _get_register_address(self, name: str) -> int:
        """Helper to get register address from name.

        Subclasses should implement this method if they support named registers.

        Args:
            name: Supported register names may include:
                - "torque_enable": Torque enable/disable register
                - "position": Position register
                - "goal_position": Goal position register
                - "velocity": Velocity register
                - "current": Current register
                - "temperature": Temperature register
                - "torque": Torque register
        """
        raise NotImplementedError("Driver does not support named registers")

    def set_torque(self, motor_id: MotorIDVar, enabled: bool) -> None:
        """
        Enable or disable motor torque.

        **Deprecated**: This legacy enable/disable API is scheduled for removal.
        Prefer driver-specific torque control APIs (`write_torque` / `read_torque`) or
        use value-level APIs where supported.

        Args:
            motor_id: Motor ID
            enabled: True to enable torque, False to disable

        """
        self.write_register(motor_id, self._get_register_address("torque_enable"), 1.0 if enabled else 0)

    def bulk_set_torque(self, motor_ids: list[MotorIDVar], enabled: bool) -> None:
        """
        Set torque for multiple motors at once (more efficient than individual calls).

        Args:
            motor_ids: List of motor IDs
            enabled: True to enable, False to disable

        """
        self.bulk_write_registers(
            {motor_id: 1.0 if enabled else 0.0 for motor_id in motor_ids},
            self._get_register_address("torque_enable"),
        )

    def get_operation_mode(self, motor_id: MotorIDVar) -> int:
        """
        Get the operation mode of a motor.

        Args:
            motor_id: Motor ID

        Returns:
            Operation mode code (driver-specific)

        """
        mode_value = self.read_register(motor_id, self._get_register_address("operation_mode"))
        return int(mode_value)

    def bulk_get_operation_mode(self, motor_ids: list[MotorIDVar]) -> dict[MotorIDVar, int]:
        """
        Get operation mode for multiple motors at once (more efficient than individual calls).

        Args:
            motor_ids: List of motor IDs
        Returns:
            Dict mapping motor_id -> operation mode code (driver-specific)

        """
        raw_modes = self.bulk_read_registers(motor_ids, self._get_register_address("operation_mode"))
        return {motor_id: int(mode_value) for motor_id, mode_value in raw_modes.items()}

    def set_operation_mode(self, motor_id: MotorIDVar, mode: int) -> None:
        """
        Set the operation mode of a motor.

        Args:
            motor_id: Motor ID
            mode: Operation mode code (driver-specific)

        """
        self.write_register(motor_id, self._get_register_address("operation_mode"), float(mode))

    def bulk_set_operation_mode(self, motor_ids: list[MotorIDVar], mode: int) -> None:
        """
        Set operation mode for multiple motors at once (more efficient than individual calls).

        Args:
            motor_ids: List of motor IDs
            mode: Operation mode code (driver-specific)

        """
        self.bulk_write_registers(
            {motor_id: float(mode) for motor_id in motor_ids},
            self._get_register_address("operation_mode"),
        )

    def get_position(self, motor_id: MotorIDVar) -> float:
        """
        Get the current position of a motor in radians.

        Args:
            motor_id: Motor ID
        
        Returns:
            Position in radians.
        """
        raw_value = self.read_register(motor_id, self._get_register_address("position"))
        return raw_value

    def bulk_get_positions(self, motor_ids: list[MotorIDVar]) -> dict[MotorIDVar, float]:
        """
        Get position for multiple motors at once (more efficient than individual calls).

        Args:
            motor_ids: List of motor IDs
        
        Returns:
            Dict mapping motor_id -> position in radians.
        """
        raw_values = self.bulk_read_registers(motor_ids, self._get_register_address("position"))
        return {motor_id: raw_value for motor_id, raw_value in raw_values.items()}

    def get_goal_position(self, motor_id: MotorIDVar) -> float:
        """
        Get the goal position of a motor in radians.

        Args:
            motor_id: Motor ID
    
        Returns:
            Goal position in radians.
        """
        raw_value = self.read_register(motor_id, self._get_register_address("goal_position"))
        return raw_value

    def bulk_get_goal_positions(self, motor_ids: list[MotorIDVar]) -> dict[MotorIDVar, float]:
        """
        Get goal position for multiple motors at once (more efficient than individual calls).

        Args:
            motor_ids: List of motor IDs

        Returns:
            Dict mapping motor_id -> goal position in radians.
        """
        raw_values = self.bulk_read_registers(motor_ids, self._get_register_address("goal_position"))
        return {motor_id: raw_value for motor_id, raw_value in raw_values.items()}

    def set_goal_position(self, motor_id: MotorIDVar, position: float) -> None:
        """
        Set the goal position of a motor in radians.

        Args:
            motor_id: Motor ID
            position: Goal position in radians.
        """
        self.write_register(motor_id, self._get_register_address("goal_position"), position)

    def bulk_set_goal_positions(self, motor_positions: dict[MotorIDVar, float]) -> None:
        """
        Set goal position for multiple motors at once (more efficient than individual calls).

        Args:
            motor_positions: Dict mapping motor IDs to goal positions in radians.
            position: Goal position in radians.
        """
        self.bulk_write_registers(
            motor_positions,
            self._get_register_address("goal_position"),
        )

    @abstractmethod
    def read_telemetry(self, motor_id: MotorIDVar, model_info: MotorModelInfo) -> MotorTelemetry:
        """
        Read real-time telemetry from a single motor.

        Args:
            motor_id: Motor ID
            model_info: `MotorModelInfo` to avoid extra identification reads

        Returns:
            Motor telemetry data.

            Excepts the position & goal_position fields are in raw units,
            others are in standard units.


            | Quantity     | Standard Unit              | Symbol |
            |--------------|----------------------------|--------|
            | Position     | radians                    | rad    |
            | Velocity     | radians per second         | rad/s  |
            | Acceleration | radians per second squared | rad/s² |
            | Current      | milliamperes               | mA     |
            | Voltage      | volts                      | V      |
            | Temperature  | degrees Celsius            | °C     |
            | Torque       | Newton-meters              | N·m    |
            | Force        | Newtons                    | N      |
            | Time         | seconds                    | s      |

        """
        pass

    def bulk_read_telemetry(self, motors: dict[MotorIDVar, MotorModelInfo]) -> dict[MotorIDVar, MotorTelemetry]:
        """
        Read telemetry from multiple motors efficiently.

        Args:
            motors: Mapping of motor_id -> MotorModelInfo (caller must supply model info)

        Returns:
            Dict mapping motor_id -> telemetry

            Excepts the position & goal_position fields are in raw units,
            others are in standard units.

            | Quantity     | Standard Unit              | Symbol |
            |--------------|----------------------------|--------|
            | Position     | radians                    | rad    |
            | Velocity     | radians per second         | rad/s  |
            | Acceleration | radians per second squared | rad/s² |
            | Current      | milliamperes               | mA     |
            | Voltage      | volts                      | V      |
            | Temperature  | degrees Celsius            | °C     |
            | Torque       | Newton-meters              | N·m    |
            | Force        | Newtons                    | N      |
            | Time         | seconds                    | s      |

        """
        result: dict[MotorIDVar, MotorTelemetry] = {}
        for motor_id, model_info in motors.items():
            telemetry = self.read_telemetry(motor_id, model_info)
            result[motor_id] = telemetry
            time.sleep(0.001)
        return result


class MotorUtil:
    """Global registry for MotorModelInfo entries.

    Register protocol table entries with `MotorUtil.register_models()` so other
    modules can perform lookups by (brand, model, variant) via `find_motor`.
    """

    _lock = RLock()
    # Keyed by (brand_lower, model_lower, variant_lower|None)
    _registry: dict[tuple[str, str, str | None], MotorModelInfo] = {}

    @classmethod
    def register_models(cls, models: list[MotorModelInfo]) -> None:
        """Register a list of MotorModelInfo entries."""
        with cls._lock:
            for m in models:
                brand = m.brand.value
                model = (m.model or "").lower()
                variant = m.variant.lower() if m.variant is not None else None
                key = (brand.lower(), model, variant)
                cls._registry[key] = m

    @classmethod
    def register_model(cls, model: MotorModelInfo) -> None:
        """Register a single MotorModelInfo entry."""
        cls.register_models([model])

    @classmethod
    def find_motor(cls, brand: str | MotorBrand, model: str, variant: str | None = None) -> MotorModelInfo | None:
        """Find a MotorModelInfo by brand, model, and optional variant.

        Matching is case-insensitive. If no exact variant match is found, the
        method will fall back to a base model (variant==None) for the same
        brand/model if present.
        """
        brand_str = (getattr(brand, "value", str(brand)) or "").lower()
        model_str = (model or "").lower()
        variant_str = variant.lower() if variant else None

        with cls._lock:
            # Exact match
            candidate = cls._registry.get((brand_str, model_str, variant_str))
            if candidate:
                return candidate
            # Fallback to base model (variant==None)
            candidate = cls._registry.get((brand_str, model_str, None))
            if candidate:
                return candidate
            # Not found
            return None
