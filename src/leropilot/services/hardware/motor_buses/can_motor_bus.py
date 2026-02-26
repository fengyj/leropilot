"""CANMotorBus implementation for CAN-based motors (Damiao)."""

import logging

from leropilot.exceptions import OperationalError
from leropilot.models.hardware import MotorModelInfo

from ..motor_drivers.base import BaseMotorDriver
from .motor_bus import MotorBus

logger = logging.getLogger(__name__)


class CANMotorBus(MotorBus):
    """MotorBus implementation for CAN-based motors (Damiao).

    This bus handles CAN communication for CAN-based servo motors.
    """

    def __init__(
        self,
        driver_class: type[BaseMotorDriver] | None = None,
    ) -> None:
        """Initialize CANMotorBus.

        Args:
            driver_class: Motor driver class to use (DamiaoDriver, etc.)

        Call :meth:`connect` with ``interface`` and ``bitrate`` to establish
        a physical connection.
        """
        super().__init__()
        self.driver_class = driver_class

    def connect(self, interface: str, baud_rate: int = 1000000) -> None:
        """Connect to CAN motor bus.

        Args:
            interface: CAN interface (e.g., "can0", "can1")
            baud_rate: CAN bitrate

        Raises:
            OperationalError: If connection fails.
        """
        if self._connected:
            return

        self.interface = interface
        self.baud_rate = baud_rate
        try:
            # For CAN buses, we don't need to pre-connect since drivers handle their own connections
            self._connected = True
            logger.info(f"Connected to CAN motor bus on {self.interface} @ {self.baud_rate} bps")
        except Exception as e:
            logger.error(f"Failed to connect CAN motor bus: {e}")
            raise OperationalError(
                i18n_key="hardware.robot_device.connect_failed",
                retriable=True,
                interface=self.interface,
            ) from e

    def disconnect(self) -> None:
        """Disconnect from CAN motor bus.

        Raises:
            OperationalError: If disconnection fails.
        """
        try:
            # Disconnect shared driver
            if self.driver:
                self.driver.disconnect()
                self.driver = None

            self._connected = False
            logger.info("Disconnected from CAN motor bus")
        except Exception as e:
            logger.error(f"Error disconnecting CAN motor bus: {e}")
            raise OperationalError(
                i18n_key="hardware.robot_device.disconnect_failed",
                retriable=False,
                interface=self.interface,
            ) from e

    def scan_motors(self, id_range: list[int] | None = None) -> dict[int, MotorModelInfo]:
        """Scan for motors on the CAN bus and return mapping id -> MotorModelInfo.

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

        discovered: dict[int, MotorModelInfo] = {}

        try:
            # Use shared driver for scanning
            motor_map = self.driver.scan_motors(id_range)

            # Register discovered motors (only store motor_info, driver is shared)
            for motor_id, model_info in motor_map.items():
                self.register_motor(motor_id, model_info)
                discovered[motor_id] = model_info

        except Exception as e:
            logger.error(f"Error scanning CAN motors: {e}")
            raise OperationalError(
                i18n_key="hardware.motor_device.scan_failed",
                retriable=True,
                interface=self.interface,
            ) from e

        logger.info(f"CAN motor scan complete: found {len(discovered)} motors")
        return discovered
