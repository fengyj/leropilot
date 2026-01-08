"""
Abstract base driver for motor bus communication.

All motor drivers inherit from this base class and implement protocol-specific logic.
"""

from abc import ABC, abstractmethod
from threading import RLock
from typing import Generic, Literal, TypeVar

from typing_extensions import Self

from leropilot.models.hardware import MotorBrand, MotorModelInfo, MotorTelemetry

# Generic motor id type for drivers
MotorID = TypeVar("MotorID")


class BaseMotorDriver(ABC, Generic[MotorID]):
    """Abstract base class for motor bus drivers"""

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
    def connect(self) -> bool:
        """
        Connect to the motor bus.

        Returns:
            True if connection successful, False otherwise
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

    @abstractmethod
    def ping_motor(self, motor_id: MotorID) -> bool:
        """
        Check if motor with given ID is on the bus.

        Args:
            motor_id: Motor ID (type depends on protocol / MotorBus)

        Returns:
            True if motor responds
        """
        pass

    @abstractmethod
    def scan_motors(self, scan_range: list[int] | None = None) -> dict[MotorID, MotorModelInfo]:
        """
        Scan motor bus and discover all motors.

        Args:
            scan_range: List of motor IDs to scan (default: 1-253)

        Returns:
            Mapping of motor id -> MotorModelInfo for discovered motors
        """
        pass

    @abstractmethod
    def read_telemetry(self, motor_id: MotorID) -> MotorTelemetry | None:
        """
        Read real-time telemetry from a single motor.

        Args:
            motor_id: Motor ID

        Returns:
            Motor telemetry data or None if read fails
        """
        pass

    @abstractmethod
    def read_bulk_telemetry(self, motor_ids: list[MotorID]) -> dict[MotorID, MotorTelemetry]:
        """
        Read telemetry from multiple motors efficiently.

        Args:
            motor_ids: List of motor IDs

        Returns:
            Dict mapping motor_id -> telemetry
        """
        pass

    @abstractmethod
    def identify_model(
        self,
        motor_id: MotorID,
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
    def set_position(self, motor_id: MotorID, position: int, speed: int | None = None) -> bool:
        """
        Set motor target position.

        Args:
            motor_id: Motor ID
            position: Target position (raw encoder units or raw values)
            speed: Optional movement speed

        Returns:
            True if command sent successfully
        """
        pass

    @abstractmethod
    def set_torque(self, motor_id: MotorID, enabled: bool) -> bool:
        """
        Enable or disable motor torque.

        Args:
            motor_id: Motor ID
            enabled: True to enable torque, False to disable

        Returns:
            True if command sent successfully
        """
        pass

    @abstractmethod
    def reboot_motor(self, motor_id: MotorID) -> bool:
        """
        Reboot a single motor.

        Args:
            motor_id: Motor ID

        Returns:
            True if reboot command sent
        """
        pass

    @abstractmethod
    def bulk_set_torque(self, motor_ids: list[MotorID], enabled: bool) -> bool:
        """
        Set torque for multiple motors at once (more efficient than individual calls).

        Args:
            motor_ids: List of motor IDs
            enabled: True to enable, False to disable

        Returns:
            True if all commands sent successfully
        """
        pass

    # Convenience aliases for telemetry session compatibility
    def write_goal_position(self, motor_id: MotorID, position: int) -> bool:
        """Alias for set_position for telemetry session compatibility.

        Use the generic `MotorID` type so callers using protocol-specific ids
        (e.g., tuples for damiao) type-check correctly.
        """
        return self.set_position(motor_id, position)

    def write_torque_enable(self, motor_id: MotorID, enabled: bool) -> bool:
        """Alias for set_torque for telemetry session compatibility."""
        return self.set_torque(motor_id, enabled)

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


# Utility registry for protocol model lookups


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
                brand = m.brand.value if m.brand is not None else ""
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
