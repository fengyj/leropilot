"""SerialMotorBus implementation for serial-based motors (Feetech, Dynamixel)."""

import logging

from leropilot.exceptions import OperationalError
from leropilot.models.hardware import MotorModelInfo

from ..motor_drivers.base import BaseMotorDriver
from .motor_bus import MotorBus

logger = logging.getLogger(__name__)


class SerialMotorBus(MotorBus):
    """MotorBus implementation for serial-based motors (Feetech, Dynamixel).

    This bus handles serial communication and can work with different serial motor drivers.
    """

    def __init__(
        self,
        driver_class: type[BaseMotorDriver] | None = None,
    ) -> None:
        """Initialize SerialMotorBus.

        Args:
            driver_class: Motor driver class to use (FeetechDriver, DynamixelDriver, etc.)

        Call :meth:`connect` with ``interface`` and ``baud_rate`` to establish
        a physical connection.
        """
        super().__init__()
        self.driver_class = driver_class

    def connect(self, interface: str, baud_rate: int = 1000000) -> None:
        """Connect to serial motor bus.

        Args:
            interface: Serial port (e.g., "COM1", "/dev/ttyUSB0")
            baud_rate: Serial baudrate

        Raises:
            OperationalError: If connection fails.
        """
        if self._connected:
            return

        self.interface = interface
        self.baud_rate = baud_rate
        try:
            # For serial buses, we don't need to pre-connect since drivers handle their own connections
            self._connected = True
            logger.info(f"Connected to serial motor bus on {self.interface} @ {self.baud_rate} baud")
        except Exception as e:
            logger.error(f"Failed to connect serial motor bus: {e}")
            raise OperationalError(
                i18n_key="hardware.robot_device.connect_failed",
                retriable=True,
                interface=self.interface,
            ) from e

    def disconnect(self) -> None:
        """Disconnect from serial motor bus.

        Raises:
            OperationalError: If disconnection fails.
        """
        try:
            # Disconnect shared driver
            if self.driver:
                self.driver.disconnect()
                self.driver = None

            self._connected = False
            logger.info("Disconnected from serial motor bus")
        except Exception as e:
            logger.error(f"Error disconnecting serial motor bus: {e}")
            raise OperationalError(
                i18n_key="hardware.robot_device.disconnect_failed",
                retriable=False,
                interface=self.interface,
            ) from e

    def scan_motors(self, id_range: list[int] | None = None) -> dict[int, MotorModelInfo]:
        """Scan for motors on the serial bus and return mapping id -> MotorModelInfo.

        Raises:
            OperationalError: If the bus is not connected.
        """
        if not self._connected or not self.driver:
            raise OperationalError(
                i18n_key="hardware.motor_device.scan_failed",
                retriable=False,
                interface=self.interface,
            )

        if id_range is None:
            id_range = list(range(1, 254))

        discovered: dict[int, MotorModelInfo] = {}

        try:
            # Use shared driver for scanning
            motor_map = self.driver.scan_motors(id_range)

            # Register discovered motors (only store motor_info, driver is shared)
            for motor_id, model_info in motor_map.items():
                self.register_motor(motor_id, model_info)
                discovered[motor_id] = model_info

        except Exception as e:
            logger.error(f"Error scanning serial motors: {e}")
            raise OperationalError(
                i18n_key="hardware.motor_device.scan_failed",
                retriable=True,
                interface=self.interface,
            ) from e

        logger.info(f"Serial motor scan complete: found {len(discovered)} motors")
        return discovered
