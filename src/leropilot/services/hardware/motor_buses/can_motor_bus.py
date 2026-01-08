"""CANMotorBus implementation for CAN-based motors (Damiao)."""

import logging

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
        interface: str,
        bitrate: int = 1000000,
        driver_class: type[BaseMotorDriver] | None = None,
    ) -> None:
        """Initialize CANMotorBus.

        Args:
            interface: CAN interface (e.g., "can0", "can1")
            bitrate: CAN bitrate
            driver_class: Motor driver class to use (DamiaoDriver, etc.)
        """
        super().__init__(interface, bitrate)
        self.driver_class = driver_class

    def connect(self) -> bool:
        """Connect to CAN motor bus."""
        if self._connected:
            return True

        try:
            # For CAN buses, we don't need to pre-connect since drivers handle their own connections
            self._connected = True
            logger.info(f"Connected to CAN motor bus on {self.interface} @ {self.baud_rate} bps")
            return True
        except Exception as e:
            logger.error(f"Failed to connect CAN motor bus: {e}")
            return False

    def disconnect(self) -> bool:
        """Disconnect from CAN motor bus."""
        try:
            # Disconnect all motor drivers
            for driver, _ in self.motors.values():
                try:
                    driver.disconnect()
                except Exception:
                    pass

            self._connected = False
            logger.info("Disconnected from CAN motor bus")
            return True
        except Exception as e:
            logger.error(f"Error disconnecting CAN motor bus: {e}")
            return False

    def scan_motors(self, id_range: list[int] | None = None) -> dict[int, MotorModelInfo]:
        """Scan for motors on the CAN bus and return mapping id -> MotorModelInfo."""
        if not self._connected or not self.driver_class:
            return {}

        if id_range is None:
            id_range = list(range(1, 128))  # CAN typically uses smaller ID range

        discovered: dict[int, MotorModelInfo] = {}

        # Create a temporary driver instance for scanning
        temp_driver = self.driver_class(self.interface, self.baud_rate)

        try:
            with temp_driver:
                motor_map = temp_driver.scan_motors(id_range)

                # Register discovered motors
                for motor_id, model_info in motor_map.items():
                    # Create driver instance for this motor
                    motor_driver = self.driver_class(self.interface, self.baud_rate)
                    self.register_motor(motor_id, motor_driver, model_info)
                    discovered[motor_id] = model_info

        except Exception as e:
            logger.error(f"Error scanning CAN motors: {e}")

        logger.info(f"CAN motor scan complete: found {len(discovered)} motors")
        return discovered
