"""DamiaoMotorBus implementation specifically for Damiao CAN motors."""

import logging

from leropilot.exceptions import OperationalError
from leropilot.models.hardware import MotorModelInfo

from ..motor_drivers.damiao.drivers import DamiaoCAN_Driver
from .motor_bus import MotorBus

logger = logging.getLogger(__name__)


class DamiaoMotorBus(MotorBus[tuple[int, int]]):
    """MotorBus implementation specifically for Damiao CAN motors.

    Uses DamiaoCAN_Driver for CAN communication with Damiao motors.
    """

    def __init__(
        self,
        interface: str,
        bitrate: int = 1000000,
    ) -> None:
        """Initialize DamiaoMotorBus.

        Args:
            interface: CAN interface in format "type:channel" (e.g., "socketcan:can0", "pcan:PCAN_USBBUS1")
            bitrate: CAN bitrate (default: 1000000)
        """
        super().__init__(interface, bitrate)
        self.driver_class = DamiaoCAN_Driver

    @classmethod
    def supported_baudrates(cls) -> list[int]:
        """CAN bitrates commonly used for Damiao motors (in suggested order)."""
        return [1000000, 500000, 250000, 2000000]

    def connect(self) -> None:
        """Connect to Damiao CAN motor bus and create shared driver.

        Raises:
            OperationalError: If connection fails.
        """
        if self._connected and self.driver:
            return

        try:
            # Create shared driver instance for all motors on this CAN bus
            self.driver = DamiaoCAN_Driver(self.interface, self.baud_rate)
            # driver.connect() will raise OperationalError on failure
            self.driver.connect()
            self._connected = True
            logger.info(f"Connected to Damiao CAN motor bus on {self.interface}")
        except OperationalError:
            raise
        except Exception as e:
            logger.error(f"Failed to connect to Damiao CAN motor bus: {e}")
            self.driver = None
            raise OperationalError(
                i18n_key="hardware.robot_device.connect_failed",
                retriable=True,
                interface=self.interface,
            ) from e

    def disconnect(self) -> None:
        """Disconnect from Damiao CAN motor bus.

        Raises:
            OperationalError: If disconnection fails.
        """
        try:
            # Disconnect shared driver
            if self.driver:
                self.driver.disconnect()
                self.driver = None

            self._connected = False
            logger.info("Disconnected from Damiao CAN motor bus")
        except Exception as e:
            logger.error(f"Error disconnecting Damiao CAN motor bus: {e}")
            raise OperationalError(
                i18n_key="hardware.robot_device.disconnect_failed",
                retriable=False,
                interface=self.interface,
            ) from e

    def scan_motors(self, id_range: list[int] | None = None) -> dict[tuple[int, int], MotorModelInfo]:
        """Scan for Damiao motors on the CAN bus. Returns mapping (send,recv) -> MotorModelInfo.

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
            id_range = list(range(1, 128))  # CAN typically uses smaller ID range

        discovered: dict[tuple[int, int], MotorModelInfo] = {}

        try:
            # Use shared driver for scanning
            motor_map = self.driver.scan_motors(id_range)

            # Register discovered motors (only store motor_info, driver is shared)
            for motor_id, model_info in motor_map.items():
                self.register_motor(motor_id, model_info)
                discovered[motor_id] = model_info

        except Exception as e:
            # Wrap any exception into an operation-level OperationalError and preserve
            # cause information in `data` for debugging.
            logger.error(f"Error scanning Damiao CAN motors: {e}")
            raise OperationalError(
                i18n_key="hardware.motor_device.scan_failed",
                retriable=True,
                interface=self.interface,
            ) from e

        logger.info(f"Damiao CAN motor scan complete: found {len(discovered)} motors")
        return discovered
