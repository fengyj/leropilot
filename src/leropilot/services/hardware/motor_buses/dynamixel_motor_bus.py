"""DynamixelMotorBus implementation specifically for Dynamixel servo motors."""

import logging

from leropilot.exceptions import OperationalError
from leropilot.models.hardware import MotorModelInfo

from ..motor_drivers.dynamixel.drivers import DynamixelDriver
from .motor_bus import MotorBus

logger = logging.getLogger(__name__)


class DynamixelMotorBus(MotorBus[int]):
    """MotorBus implementation specifically for Dynamixel servo motors.

    Uses DynamixelDriver for serial communication with Dynamixel Protocol 2.0 motors.
    """

    def __init__(
        self,
        interface: str,
        baud_rate: int = 1000000,
    ) -> None:
        """Initialize DynamixelMotorBus.

        Args:
            interface: Serial port (e.g., "COM1", "/dev/ttyUSB0")
            baud_rate: Serial baudrate (default: 1000000)
        """
        super().__init__(interface, baud_rate)
        self.driver_class = DynamixelDriver

    @classmethod
    def supported_baudrates(cls) -> list[int]:
        """Dynamixel preferred baud rates (descending order)."""
        return [1000000, 115200]

    def connect(self) -> None:
        """Connect to Dynamixel motor bus and create shared driver.

        Raises:
            OperationalError: If connection fails.
        """
        if self._connected and self.driver:
            return

        try:
            # Create shared driver instance for all motors on this bus
            self.driver = DynamixelDriver(self.interface, self.baud_rate)
            # driver.connect() will raise OperationalError on failure
            self.driver.connect()
            self._connected = True
            logger.info(f"Connected to Dynamixel motor bus on {self.interface} @ {self.baud_rate} baud")
        except OperationalError:
            raise
        except Exception as e:
            logger.error(f"Failed to connect Dynamixel motor bus: {e}")
            self.driver = None
            raise OperationalError(
                i18n_key="hardware.robot_device.connect_failed",
                retriable=True,
                interface=self.interface,
            ) from e

    def disconnect(self) -> None:
        """Disconnect from Dynamixel motor bus.

        Raises:
            OperationalError: If disconnection fails.
        """
        try:
            # Disconnect shared driver
            if self.driver:
                self.driver.disconnect()
                self.driver = None

            self._connected = False
            logger.info("Disconnected from Dynamixel motor bus")
        except Exception as e:
            logger.error(f"Error disconnecting Dynamixel motor bus: {e}")
            raise OperationalError(
                i18n_key="hardware.robot_device.disconnect_failed",
                retriable=False,
                interface=self.interface,
            ) from e

    def scan_motors(self, id_range: list[int] | None = None) -> dict[int, MotorModelInfo]:
        """Scan for Dynamixel motors on the bus and return mapping id -> MotorModelInfo.

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
            id_range = list(range(1, 253))  # Dynamixel supports up to 252 motors

        discovered: dict[int, MotorModelInfo] = {}

        try:
            # Use shared driver for scanning
            motor_map = self.driver.scan_motors(id_range)

            # Register discovered motors (only store motor_info, driver is shared)
            for motor_id, model_info in motor_map.items():
                self.register_motor(motor_id, model_info)
                discovered[motor_id] = model_info

        except Exception as e:
            logger.error(f"Error scanning Dynamixel motors: {e}")
            raise OperationalError(
                i18n_key="hardware.motor_device.scan_failed",
                retriable=True,
                interface=self.interface,
            ) from e

        logger.info(f"Dynamixel motor scan complete: found {len(discovered)} motors")
        return discovered
