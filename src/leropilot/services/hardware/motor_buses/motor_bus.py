"""MotorBus base class providing unified motor control interface.

MotorBus provides a unified interface for motor control operations, following the
lerobot-inspired architecture where different MotorBus subclasses handle different
communication protocols and use appropriate drivers directly.
"""

import logging
from abc import ABC, abstractmethod
from typing import Generic

from leropilot.models.hardware import MotorModelInfo, MotorTelemetry

from ..motor_drivers.base import BaseMotorDriver, MotorID

# Do not redefine MotorID here; use the typevar from the driver base

logger = logging.getLogger(__name__)


class MotorBus(ABC, Generic[MotorID]):
    """Abstract base class for motor bus implementations.

    MotorBus provides a unified interface for motor control operations.
    Different subclasses handle different communication protocols (serial, CAN, etc.)
    and use appropriate driver implementations directly.
    """

    def __init__(
        self,
        interface: str,
        baud_rate: int | None = None,
    ) -> None:
        """Initialize MotorBus.

        Args:
            interface: Communication interface (serial port, CAN interface, etc.)
            baud_rate: Communication baudrate/bitrate
        """
        self.interface = interface
        self.baud_rate = baud_rate
        # Map motor_id -> (driver, MotorModelInfo | None)
        self.motors: dict[MotorID, tuple[BaseMotorDriver[MotorID], MotorModelInfo | None]] = {}
        self._connected = False

    @abstractmethod
    def connect(self) -> bool:
        """Connect to the motor bus."""
        pass

    @abstractmethod
    def disconnect(self) -> bool:
        """Disconnect from the motor bus."""
        pass

    def is_connected(self) -> bool:
        """Check if bus is connected."""
        return self._connected

    @abstractmethod
    def scan_motors(self, id_range: list[int] | None = None) -> dict[MotorID, MotorModelInfo]:
        """Scan bus for motors and return mapping motor_id -> MotorModelInfo."""
        pass

    def register_motor(
        self,
        motor_id: MotorID,
        driver: BaseMotorDriver[MotorID],
        motor_info: MotorModelInfo | None = None,
    ) -> None:
        """Register a motor driver with the bus using an explicit motor_id and optional MotorModelInfo."""
        if motor_id is None:
            raise ValueError("motor_id must be provided when registering a driver")
        self.motors[motor_id] = (driver, motor_info)

    def get_motor(self, motor_id: MotorID) -> BaseMotorDriver[MotorID] | None:
        """Get motor driver by ID (returns driver instance or None)."""
        entry = self.motors.get(motor_id)
        return entry[0] if entry is not None else None

    def get_motor_info(self, motor_id: MotorID) -> MotorModelInfo | None:
        """Return the MotorModelInfo object associated with a registered motor, if any."""
        entry = self.motors.get(motor_id)
        return entry[1] if entry is not None else None

    def ping_motor(self, motor_id: MotorID) -> bool:
        """Ping a motor to check if it's responsive."""
        driver = self.get_motor(motor_id)
        if driver:
            return driver.ping_motor(motor_id)
        return False

    def read_telemetry(self, motor_id: MotorID) -> MotorTelemetry | None:
        """Read telemetry from a single motor."""
        driver = self.get_motor(motor_id)
        if driver:
            return driver.read_telemetry(motor_id)
        return None

    def read_bulk_telemetry(self, motor_ids: list[MotorID]) -> dict[MotorID, MotorTelemetry]:
        """Read telemetry from multiple motors."""
        results: dict[MotorID, MotorTelemetry] = {}
        for motor_id in motor_ids:
            telemetry = self.read_telemetry(motor_id)
            if telemetry:
                results[motor_id] = telemetry
        return results

    def set_position(self, motor_id: MotorID, position: int, speed: int | None = None) -> bool:
        """Set motor position."""
        driver = self.get_motor(motor_id)
        if driver:
            return driver.set_position(motor_id, position, speed)
        return False

    def set_torque(self, motor_id: MotorID, enabled: bool) -> bool:
        """Enable/disable motor torque."""
        driver = self.get_motor(motor_id)
        if driver:
            return driver.set_torque(motor_id, enabled)
        return False

    def bulk_set_torque(self, motor_ids: list[MotorID], enabled: bool) -> bool:
        """Set torque for multiple motors."""
        success = True
        for motor_id in motor_ids:
            if not self.set_torque(motor_id, enabled):
                success = False
        return success

    def reboot_motor(self, motor_id: MotorID) -> bool:
        """Reboot a motor."""
        driver = self.get_motor(motor_id)
        if driver:
            return driver.reboot_motor(motor_id)
        return False

    @staticmethod
    def serial_types() -> list[type]:
        """Return MotorBus subclasses that use serial interfaces.

        These class objects correspond to the implementations accepted by
        :meth:`create` for serial-based bus implementations.
        """
        # Import lazily to avoid import cycles
        from .dynamixel_motor_bus import DynamixelMotorBus
        from .feetech_motor_bus import FeetechMotorBus

        return [FeetechMotorBus, DynamixelMotorBus]

    @staticmethod
    def can_types() -> list[type]:
        """Return MotorBus subclasses that use CAN interfaces."""
        from .damiao_motor_bus import DamiaoMotorBus

        return [DamiaoMotorBus]

    # Abstract class-level API -------------------------------------------------
    @classmethod
    @abstractmethod
    def supported_baudrates(cls) -> list[int]:
        """Return list of supported baud/bit rates for this MotorBus implementation.

        The list must be ordered by preferred priority (highest-likelihood first).
        Subclasses MUST implement this method.
        """
        raise NotImplementedError

    @staticmethod
    @staticmethod
    def resolve_bus_class(motorbus_type: str | type["MotorBus"]) -> type["MotorBus"]:
        """Resolve a motorbus type identifier (string or class) to a MotorBus class.

        Public helper; centralizes mapping logic and avoids duplication.
        """
        # If it's already a class, return it
        if isinstance(motorbus_type, type):
            return motorbus_type

        key = str(motorbus_type).strip().lower().replace("_", "").replace("-", "")

        if key in ("feetech", "feetechmotorbus"):
            from .feetech_motor_bus import FeetechMotorBus

            return FeetechMotorBus
        elif key in ("dynamixel", "dynamixelmotorbus"):
            from .dynamixel_motor_bus import DynamixelMotorBus

            return DynamixelMotorBus
        elif key in ("damiao", "damiaomotorbus", "can", "canmotorbus"):
            from .damiao_motor_bus import DamiaoMotorBus

            return DamiaoMotorBus
        else:
            raise ValueError(f"Unknown MotorBus type: {motorbus_type}")

    @staticmethod
    def supported_baudrates_for(motorbus_type: str | type["MotorBus"]) -> list[int]:
        """Return supported baudrates for a given motorbus type (string or class)."""
        cls = MotorBus.resolve_bus_class(motorbus_type)
        return cls.supported_baudrates()

    # Context manager support
    def __enter__(self) -> "MotorBus":
        self.connect()
        return self

    def __exit__(self, exc_type: type | None, exc_val: BaseException | None, exc_tb: object | None) -> None:
        self.disconnect()

    @staticmethod
    def create(motorbus_type: str | type["MotorBus"], interface: str, baud_rate: int | None = None) -> "MotorBus":
        """
        Factory method to create a MotorBus instance based on type name.

        Args:
            motorbus_type: Either a string identifier (e.g., "feetech", "dynamixel", "damiao")
                          or a MotorBus subclass reference.
            interface: Interface identifier (serial port or CAN interface)
            baud_rate: Optional baud/bit rate (passes through to the constructor)

        Returns:
            An instance of a MotorBus subclass.

        Raises:
            ValueError: If the motorbus_type is unknown.
        """
        # Resolve class and instantiate
        cls = MotorBus.resolve_bus_class(motorbus_type) if not isinstance(motorbus_type, type) else motorbus_type
        return cls(interface, baud_rate)
