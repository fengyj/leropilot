"""SerialMotorBus implementation for serial-based motors (Feetech, Dynamixel)."""

import logging

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
        interface: str,
        baud_rate: int = 1000000,
        driver_class: type[BaseMotorDriver] | None = None,
    ) -> None:
        """Initialize SerialMotorBus.

        Args:
            interface: Serial port (e.g., "COM1", "/dev/ttyUSB0")
            baud_rate: Serial baudrate
            driver_class: Motor driver class to use (FeetechDriver, DynamixelDriver, etc.)
        """
        super().__init__(interface, baud_rate)
        self.driver_class = driver_class

    def connect(self) -> bool:
        """Connect to serial motor bus."""
        if self._connected:
            return True

        try:
            # For serial buses, we don't need to pre-connect since drivers handle their own connections
            self._connected = True
            logger.info(f"Connected to serial motor bus on {self.interface} @ {self.baud_rate} baud")
            return True
        except Exception as e:
            logger.error(f"Failed to connect serial motor bus: {e}")
            return False

    def disconnect(self) -> bool:
        """Disconnect from serial motor bus."""
        try:
            # Disconnect all motor drivers
            for driver, _ in self.motors.values():
                try:
                    driver.disconnect()
                except Exception:
                    pass

            self._connected = False
            logger.info("Disconnected from serial motor bus")
            return True
        except Exception as e:
            logger.error(f"Error disconnecting serial motor bus: {e}")
            return False

    def scan_motors(self, id_range: list[int] | None = None) -> dict[int, MotorModelInfo]:
        """Scan for motors on the serial bus and return mapping id -> MotorModelInfo."""
        if not self._connected or not self.driver_class:
            return {}

        if id_range is None:
            id_range = list(range(1, 254))

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
            logger.error(f"Error scanning serial motors: {e}")

        logger.info(f"Serial motor scan complete: found {len(discovered)} motors")
        return discovered
