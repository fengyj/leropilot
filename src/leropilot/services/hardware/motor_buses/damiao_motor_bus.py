"""DamiaoMotorBus implementation specifically for Damiao CAN motors."""

import logging

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
            interface: CAN interface (e.g., "can0", "can1")
            bitrate: CAN bitrate (default: 1000000)
        """
        super().__init__(interface, bitrate)
        self.driver_class = DamiaoCAN_Driver

    @classmethod
    def supported_baudrates(cls) -> list[int]:
        """CAN bitrates commonly used for Damiao motors (in suggested order)."""
        return [1000000, 500000, 250000, 2000000]

    def connect(self) -> bool:
        """Connect to Damiao CAN motor bus."""
        # For CAN-based buses, we don't need a persistent "test" connection
        # because the actual communication happens during scan_motors or
        # when individual motor drivers are used.
        self._connected = True
        return True

    def disconnect(self) -> bool:
        """Disconnect from Damiao CAN motor bus."""
        try:
            # Disconnect all motor drivers
            for driver, _ in self.motors.values():
                try:
                    driver.disconnect()
                except Exception:
                    pass

            self._connected = False
            logger.debug("Disconnected from Damiao CAN motor bus")
            return True
        except Exception as e:
            logger.error(f"Error disconnecting Damiao CAN motor bus: {e}")
            return False

    def scan_motors(self, id_range: list[int] | None = None) -> dict[tuple[int, int], MotorModelInfo]:
        """Scan for Damiao motors on the CAN bus. Returns mapping (send,recv) -> MotorModelInfo."""
        if not self._connected:
            return {}

        if id_range is None:
            id_range = list(range(1, 128))  # CAN typically uses smaller ID range

        discovered: dict[tuple[int, int], MotorModelInfo] = {}

        # Create a temporary driver instance for scanning
        temp_driver = DamiaoCAN_Driver(self.interface, self.baud_rate)

        try:
            with temp_driver:
                motor_map = temp_driver.scan_motors(id_range)

                # Register discovered motors
                for motor_id, model_info in motor_map.items():
                    # Create driver instance for this motor
                    motor_driver = DamiaoCAN_Driver(self.interface, self.baud_rate)

                    # Normalize to tuple send/recv
                    if isinstance(motor_id, (list, tuple)):
                        mid = (int(motor_id[0]), int(motor_id[1]))
                    else:
                        mid = (int(motor_id), int(motor_id))

                    self.register_motor(mid, motor_driver, model_info)
                    discovered[mid] = model_info

        except Exception as e:
            logger.error(f"Error scanning Damiao CAN motors: {e}")

        logger.info(f"Damiao CAN motor scan complete: found {len(discovered)} motors")
        return discovered
