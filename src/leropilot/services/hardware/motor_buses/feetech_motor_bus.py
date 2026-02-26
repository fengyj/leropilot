"""FeetechMotorBus implementation specifically for Feetech servo motors."""

import logging

from leropilot.exceptions import OperationalError
from leropilot.models.hardware import MotorModelInfo

from ..motor_drivers.feetech.drivers import FeetechDriver
from .motor_bus import MotorBus

logger = logging.getLogger(__name__)


class FeetechMotorBus(MotorBus[int]):
    """MotorBus implementation specifically for Feetech servo motors.

    Uses FeetechDriver for serial communication with Feetech SCS/ST servos.
    """

    def __init__(self) -> None:
        """Initialize FeetechMotorBus.

        Call :meth:`connect` with ``interface`` and ``baud_rate`` to establish
        a physical connection.
        """
        super().__init__()
        self.driver_class = FeetechDriver
        
    @classmethod
    def supported_baudrates(cls) -> list[int]:
        """Feetech preferred baud rates (descending order of likelihood)."""
        # Common Feetech baudrates (try 1_000_000 first, then common serial rates)
        return [1000000, 115200]

    def connect(self, interface: str, baud_rate: int = 1000000) -> None:
        """Connect to Feetech motor bus and create shared driver.

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
            self.driver = FeetechDriver(self.interface, self.baud_rate)
            # driver.connect() will raise OperationalError on failure
            self.driver.connect()
            self._connected = True
            logger.info(f"Connected to Feetech motor bus on {self.interface} @ {self.baud_rate} baud")
        except OperationalError:
            raise
        except Exception as e:
            logger.error(f"Failed to connect Feetech motor bus: {e}")
            self.driver = None
            raise OperationalError(
                i18n_key="hardware.robot_device.connect_failed",
                retriable=True,
                interface=self.interface,
            ) from e

    def disconnect(self) -> None:
        """Disconnect from Feetech motor bus.

        Raises:
            OperationalError: If disconnection fails.
        """
        try:
            # Disconnect shared driver
            if self.driver:
                self.driver.disconnect()
                self.driver = None

            self._connected = False
            logger.info("Disconnected from Feetech motor bus")
        except Exception as e:
            logger.error(f"Error disconnecting Feetech motor bus: {e}")
            raise OperationalError(
                i18n_key="hardware.robot_device.disconnect_failed",
                retriable=False,
                interface=self.interface,
            ) from e

    def scan_motors(self, id_range: list[int] | None = None) -> dict[int, MotorModelInfo]:
        """Scan for Feetech motors on the bus and return mapping id -> MotorModelInfo.

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
            id_range = list(range(1, 254))  # Feetech supports up to 253 motors

        discovered: dict[int, MotorModelInfo] = {}

        try:
            # Use shared driver for scanning (may raise OperationalError on comm failure)
            motor_map = self.driver.scan_motors(id_range)

            # Register discovered motors (only store motor_info, driver is shared)
            for motor_id, model_info in motor_map.items():
                self.register_motor(motor_id, model_info)
                discovered[motor_id] = model_info

        except Exception as e:
            # Wrap any exception into an operation-level OperationalError and
            # preserve cause information in `data` for debugging.
            logger.error(f"Error scanning Feetech motors: {e}")
            raise OperationalError(
                i18n_key="hardware.motor_device.scan_failed",
                retriable=True,
                interface=self.interface,
            ) from e

        logger.info(f"Feetech motor scan complete: found {len(discovered)} motors")
        return discovered

    def set_half_turn_homings(self, motor_ids: list[int]) -> None:
        """Set the current position of each motor as its halfway home reference.

        For each motor this method:
        1. Temporarily resets the calibration homing offset and range to defaults.
        2. Reads the current raw encoder position.
        3. Computes ``homing_offset = (encoder_resolution - 1) / 2 - current_position``
           so that mid-range becomes position 0 after offset application.
        4. Writes the computed offset back into the registered calibration.

        This is intended to be called by :class:`HalfwayCalibrator` after the user
        has physically positioned all joints at their midpoint.

        Args:
            motor_ids: List of motor IDs whose homing offsets should be updated.
        """
        from leropilot.services.hardware.motor_drivers.feetech.drivers import FeetechDriver  # type: ignore[import]
        with self._lock:
            driver = self._ensure_driver()
            assert isinstance(driver, FeetechDriver), "Driver must be FeetechDriver"
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
                    logger.error("FeetechDriver does not support write_homing_offset, cannot set zero position")
                    raise NotImplementedError(
                        "FeetechDriver does not implement write_homing_offset. "
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

    def set_zero_position(self, motor_id: int) -> None:
        """Set the current position of a motor as its software zero reference.

        Feetech motors do not have a hardware "set zero" command, so this method
        implements zero-position via a software homing offset:

        1. Temporarily resets the calibration homing offset to ``0.0``.
        2. Reads the current raw encoder position.
        3. Computes ``homing_offset = -current_position`` so the motor reports
           position ``0`` at the current physical location after offset application.

        The caller (:class:`ZeroPositionCalibrator`) is responsible for setting
        ``range_min``/``range_max`` (typically ±π/2) and persisting the updated
        calibration via ``RobotManager.update_robot``.

        Args:
            motor_id: Protocol ID of the motor whose zero point should be updated.
        """
        with self._lock:
            driver = self._ensure_driver()
            motor_info = self.motors.get(motor_id)
            if motor_info is None:
                logger.warning(f"set_zero_position: motor {motor_id} not registered, skipping")
                return

            cal = self.calibrations.get(motor_id)
            if cal is not None:
                cal.homing_offset = 0.0  # reset before reading actual position

            write_homing_offset = getattr(driver, "write_homing_offset", None)
            if write_homing_offset is None or not callable(write_homing_offset):
                logger.error("FeetechDriver does not support write_homing_offset, cannot set zero position")
                raise NotImplementedError(
                    "FeetechDriver does not implement write_homing_offset. "
                    "Add hardware-level homing offset support to the driver first."
                )
            
            write_homing_offset(motor_id, 0.0)
            current_position = int(driver.get_position(motor_id=motor_id))
            # effective = raw + homing_offset; want effective = 0 at current_position
            homing_offset = 0.0
            write_homing_offset(motor_id, current_position)

            if cal is not None:
                cal.homing_offset = homing_offset
                cal.range_min = float(-motor_info.encoder_resolution // 4)  # default ±1/4 turn range
                cal.range_max = float(motor_info.encoder_resolution // 4)
                logger.info(
                    f"set_zero_position: motor {motor_id}, "
                    f"raw_pos={current_position}, homing_offset={homing_offset:.1f}"
                )
