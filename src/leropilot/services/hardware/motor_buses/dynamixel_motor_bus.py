"""DynamixelMotorBus implementation specifically for Dynamixel servo motors."""

import logging

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
        return [1000000, 57600, 115200, 9600]

    def connect(self) -> bool:
        """Connect to Dynamixel motor bus."""
        if self._connected:
            return True

        try:
            # Create a test driver instance to verify connection
            test_driver = DynamixelDriver(self.interface, self.baud_rate)
            if test_driver.connect():
                test_driver.disconnect()  # Clean up test connection
                self._connected = True
                logger.info(f"Connected to Dynamixel motor bus on {self.interface} @ {self.baud_rate} baud")
                return True
            else:
                logger.error("Failed to connect to Dynamixel motor bus")
                return False
        except Exception as e:
            logger.error(f"Failed to connect Dynamixel motor bus: {e}")
            return False

    def disconnect(self) -> bool:
        """Disconnect from Dynamixel motor bus."""
        try:
            # Disconnect all motor drivers
            for driver, _ in self.motors.values():
                try:
                    driver.disconnect()
                except Exception:
                    pass

            self._connected = False
            logger.info("Disconnected from Dynamixel motor bus")
            return True
        except Exception as e:
            logger.error(f"Error disconnecting Dynamixel motor bus: {e}")
            return False

    def scan_motors(self, id_range: list[int] | None = None) -> dict[int, MotorModelInfo]:
        """Scan for Dynamixel motors on the bus and return mapping id -> MotorModelInfo."""
        if not self._connected:
            return {}

        if id_range is None:
            id_range = list(range(1, 253))  # Dynamixel supports up to 252 motors

        discovered: dict[int, MotorModelInfo] = {}

        # Create a temporary driver instance for scanning
        temp_driver = DynamixelDriver(self.interface, self.baud_rate)

        try:
            with temp_driver:
                motor_map = temp_driver.scan_motors(id_range)

                # Register discovered motors
                for motor_id, model_info in motor_map.items():
                    # Create driver instance for this motor
                    motor_driver = DynamixelDriver(self.interface, self.baud_rate)
                    self.register_motor(motor_id, motor_driver, model_info)
                    discovered[motor_id] = model_info

        except Exception as e:
            logger.error(f"Error scanning Dynamixel motors: {e}")

        logger.info(f"Dynamixel motor scan complete: found {len(discovered)} motors")
        return discovered
