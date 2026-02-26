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

    def __init__(self) -> None:
        """Initialize DynamixelMotorBus.

        Call :meth:`connect` with ``interface`` and ``baud_rate`` to establish
        a physical connection.
        """
        super().__init__()
        self.driver_class = DynamixelDriver

    @classmethod
    def supported_baudrates(cls) -> list[int]:
        """Dynamixel preferred baud rates (descending order)."""
        return [1000000, 115200]

    def connect(self, interface: str, baud_rate: int = 1000000) -> None:
        """Connect to Dynamixel motor bus and create shared driver.

        Args:
            interface: Serial port (e.g., "COM1", "/dev/ttyUSB0")
            baud_rate: Serial baudrate (default: 1000000)

        Raises:
            OperationalError: If connection fails.
        """
        if self._connected and self.driver:
            return

        self.interface = interface
        self.baud_rate = baud_rate
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

    def set_half_turn_homings(self, motor_ids: list[int]) -> None:
        """Set the current position of each motor as its halfway home reference.

        Identical algorithm to ``FeetechMotorBus.set_half_turn_homings``:
        computes ``homing_offset = (encoder_resolution - 1) / 2 - current_position``
        and updates the registered calibration entry.

        Args:
            motor_ids: List of motor IDs whose homing offsets should be updated.
        """
        with self._lock:
            driver = self._ensure_driver()
            for motor_id in motor_ids:
                motor_info = self.motors.get(motor_id)
                if motor_info is None:
                    logger.warning(f"set_half_turn_homings: motor {motor_id} not registered, skipping")
                    continue

                cal = self.calibrations.get(motor_id)
                if cal is not None:
                    cal.homing_offset = 0.0  # reset before reading

                resolution = motor_info.encoder_resolution
                max_res = resolution - 1

                write_homing_offset = getattr(driver, "write_homing_offset", None)
                if write_homing_offset is None or not callable(write_homing_offset):
                    logger.error("DynamixelDriver does not support write_homing_offset, cannot set zero position")
                    raise NotImplementedError(
                        "DynamixelDriver does not implement write_homing_offset. "
                        "Add hardware-level homing offset support to the driver first."
                    )
                
                write_homing_offset(motor_id, 0.0)
                current_position = int(driver.get_position(motor_id=motor_id))
                homing_offset = float(int(max_res / 2) - current_position)
                write_homing_offset(motor_id, homing_offset)

                if cal is not None:
                    cal.homing_offset = homing_offset
                    cal.range_min = 0.0
                    cal.range_max = float(max_res)
                    logger.info(
                        f"set_half_turn_homings: motor {motor_id}, "
                        f"raw_pos={current_position}, homing_offset={homing_offset:.1f}"
                    )
