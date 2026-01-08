"""FeetechMotorBus implementation specifically for Feetech servo motors."""

import logging

from leropilot.models.hardware import MotorModelInfo

from ..motor_drivers.feetech.drivers import FeetechDriver
from .motor_bus import MotorBus

logger = logging.getLogger(__name__)


class FeetechMotorBus(MotorBus[int]):
    """MotorBus implementation specifically for Feetech servo motors.

    Uses FeetechDriver for serial communication with Feetech SCS/ST servos.
    """

    def __init__(
        self,
        interface: str,
        baud_rate: int = 1000000,
    ) -> None:
        """Initialize FeetechMotorBus.

        Default baud preference order is defined in :meth:`supported_baudrates`.
        """
        """Initialize FeetechMotorBus.

        Args:
            interface: Serial port (e.g., "COM1", "/dev/ttyUSB0")
            baud_rate: Serial baudrate (default: 1000000)
        """
        super().__init__(interface, baud_rate)
        self.driver_class = FeetechDriver

    @classmethod
    def supported_baudrates(cls) -> list[int]:
        """Feetech preferred baud rates (descending order of likelihood)."""
        # Common Feetech baudrates (try 1_000_000 first, then common serial rates)
        return [1000000, 115200, 57600, 9600]

    def connect(self) -> bool:
        """Connect to Feetech motor bus."""
        if self._connected:
            return True

        try:
            # Create a test driver instance to verify connection
            test_driver = FeetechDriver(self.interface, self.baud_rate)
            if test_driver.connect():
                test_driver.disconnect()  # Clean up test connection
                self._connected = True
                logger.info(f"Connected to Feetech motor bus on {self.interface} @ {self.baud_rate} baud")
                return True
            else:
                logger.error("Failed to connect to Feetech motor bus")
                return False
        except Exception as e:
            logger.error(f"Failed to connect Feetech motor bus: {e}")
            return False

    def disconnect(self) -> bool:
        """Disconnect from Feetech motor bus."""
        try:
            # Disconnect all motor drivers
            for driver, _ in self.motors.values():
                try:
                    driver.disconnect()
                except Exception:
                    pass

            self._connected = False
            logger.info("Disconnected from Feetech motor bus")
            return True
        except Exception as e:
            logger.error(f"Error disconnecting Feetech motor bus: {e}")
            return False

    def scan_motors(self, id_range: list[int] | None = None) -> dict[int, MotorModelInfo]:
        """Scan for Feetech motors on the bus and return mapping id -> MotorModelInfo."""
        if not self._connected:
            return {}

        if id_range is None:
            id_range = list(range(1, 254))  # Feetech supports up to 253 motors

        discovered: dict[int, MotorModelInfo] = {}

        # Create a temporary driver instance for scanning
        temp_driver = FeetechDriver(self.interface, self.baud_rate)

        try:
            with temp_driver:
                motor_map = temp_driver.scan_motors(id_range)

                # Register discovered motors
                for motor_id, model_info in motor_map.items():
                    # Create driver instance for this motor
                    motor_driver = FeetechDriver(self.interface, self.baud_rate)
                    self.register_motor(motor_id, motor_driver, model_info)
                    discovered[motor_id] = model_info

        except Exception as e:
            logger.error(f"Error scanning Feetech motors: {e}")

        logger.info(f"Feetech motor scan complete: found {len(discovered)} motors")
        return discovered
