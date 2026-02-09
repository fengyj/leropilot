"""Robot telerobotics service for real-time motor control and telemetry streaming."""

import asyncio
import logging
import time
from collections import deque
from collections.abc import Callable
from types import TracebackType

from leropilot.exceptions import OperationalError
from leropilot.models.hardware import (
    DeviceStatus,
    MotorBrand,
    MotorBusData,
    MotorCalibration,
    MotorID,
    MotorLimit,
    MotorModelInfo,
    MotorTelemetry,
    PositionType,
    ProtectionStatus,
    ProtectionViolation,
    Robot,
    RobotDefinition,
    RobotTelemetryFrame,
)
from leropilot.services.hardware.motor_buses.motor_bus import MotorBus
from leropilot.services.hardware.robots.manager import get_robot_manager

logger = logging.getLogger(__name__)

# Constants
_DEFAULT_MAX_CONSECUTIVE_ERRORS = 10
_ERROR_RETRY_DELAY_SECONDS = 0.1
_HIGH_VELOCITY_WARNING_THRESHOLD = 0.8  # 80% of max velocity


class RobotTelecontrolService:
    """Service for real-time robot teleoperation and motor control.

    Provides async-based motor data acquisition and control for robots. Manages
    motor bus connections, telemetry streaming, and command execution.

    Features:
    - Async motor data acquisition with configurable FPS
    - Real FPS calculation based on actual read timing
    - Motor control operations (position, torque, velocity)
    - Calibration management (homing offsets, ranges)
    - Resource cleanup via async context manager
    - Automatic disconnection on error or session end
    """

    def __init__(self, robot: Robot, normalized: bool = False) -> None:
        """Initialize RobotTelecontrolService.

        Args:
            robot: Robot instance to control.
            normalized: If True, return normalized positions ([-1, 1]); else raw encoder units.

        Raises:
            OperationalError: If robot is not AVAILABLE or motor_bus interfaces are None.
        """
        if robot.status != DeviceStatus.AVAILABLE:
            raise OperationalError(
                i18n_key="hardware.robot_device.not_available",
                device_id=robot.id,
                reason=f"Robot status is {robot.status}, expected AVAILABLE",
            )

        if not robot.motor_bus_connections:
            raise OperationalError(
                i18n_key="hardware.robot_device.not_available",
                device_id=robot.id,
                reason="No motor bus connections configured",
            )

        # Validate motor_bus_connections: each interface must not be None
        for bus_name, conn in robot.motor_bus_connections.items():
            if conn.interface is None:
                raise OperationalError(
                    i18n_key="hardware.robot_device.not_available",
                    device_id=robot.id,
                    reason=f"Motor bus '{bus_name}' has no interface configured",
                )

        self._robot = robot
        self._normalized = normalized
        self._motor_buses: dict[str, MotorBus[MotorID]] = {}
        self._read_task: asyncio.Task | None = None
        self._running = False
        self._polling_enabled = True
        self._polling_event = asyncio.Event()
        self._polling_event.set()  # Start in enabled state

        # FPS tracking: deque of timestamps (max ~2 seconds of history)
        self._timestamp_deque: deque[float] = deque()
        self._actual_fps = 0  # Initialize as int

        # Error tracking: prevent silent infinite failures
        self._consecutive_errors = 0
        self._max_consecutive_errors = _DEFAULT_MAX_CONSECUTIVE_ERRORS

    async def __aenter__(self) -> "RobotTelecontrolService":
        """Async context manager entry."""
        return self

    async def __aexit__(
        self,
        exc_type: type | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Async context manager exit - ensures cleanup."""
        await self.stop()

    def _get_motor_bus_motor_ids(self, bus_name: str) -> list[MotorID]:
        """Get all motor IDs for a motor bus from robot definition.

        Returns:
            List of motor IDs (int or tuple) for motors on this bus.
            If motor ID is a tuple, only the first element is used.
        """
        definition = self._robot.definition
        if isinstance(definition, str) or definition is None:
            return []

        # Find motors on this specific bus
        motor_ids = []
        bus_def = definition.motor_buses.get(bus_name)
        if not bus_def:
            return []

        # bus_def.motors is dict[str, RobotMotorDefinition]
        for motor_def in bus_def.motors.values():
            # motor_def.id is MotorID (int or tuple[int, int])
            # If tuple, we use the first element (send_id)
            motor_id = motor_def.id
            if isinstance(motor_id, tuple):
                motor_ids.append(motor_id[0])
            else:
                motor_ids.append(motor_id)

        return motor_ids

    async def _names_to_ids(self, bus_name: str, motor_names: list[str] | set[str]) -> dict[str, MotorID]:
        """Convert motor logical names to MotorIDs using robot definition.

        Args:
            bus_name: Name of the motor bus.
            motor_names: Iterable of motor logical names.

        Returns:
            Mapping from motor_name to MotorID (int or tuple).
        """
        result = {}
        definition = self._robot.definition

        if not isinstance(definition, RobotDefinition):
            return result

        bus_def = definition.motor_buses.get(bus_name)
        if not bus_def:
            return result

        for motor_name in motor_names:
            motor_def = bus_def.motors.get(motor_name)
            if motor_def:
                result[motor_name] = motor_def.id

        return result

    def _merge_custom_protection_limits(self, bus: MotorBus) -> None:
        """Merge custom protection limits into bus motor info.

        Takes limits from robot.custom_protection_settings and merges them
        into the MotorModelInfo.limits for each motor on the bus.

        Args:
            bus: MotorBus instance with populated motors dict.
        """
        for motor_id, motor_info in bus.motors.items():
            if motor_info is None:
                continue

            # Look for custom limits matching this motor's brand/model/variant
            brand = motor_info.brand.value if isinstance(motor_info.brand, MotorBrand) else motor_info.brand
            model = motor_info.model
            variant = motor_info.variant

            # Try exact match first, then without variant
            custom_limits_key = (brand, model, variant)
            if custom_limits_key not in self._robot.custom_protection_settings:
                custom_limits_key = (brand, model, None)

            if custom_limits_key in self._robot.custom_protection_settings:
                custom_limit_objs = self._robot.custom_protection_settings[custom_limits_key]
                logger.debug(f"Found custom protection limits for motor {motor_id}: {len(custom_limit_objs)} limits")

                # Merge custom limits into motor_info.limits
                for limit_obj in custom_limit_objs:
                    # Ensure it's a MotorLimit instance
                    if isinstance(limit_obj, MotorLimit):
                        motor_info.limits[limit_obj.type] = limit_obj
                        logger.debug(f"Merged limit {limit_obj.type}={limit_obj.value} for motor {motor_id}")

    def _calculate_protection_status(
        self, telemetry: MotorTelemetry, motor_info: MotorModelInfo | None
    ) -> ProtectionStatus:
        """Calculate protection status for a motor based on current telemetry.

        Compares telemetry values against motor_info limits with thresholds:
        - 85% of limit → warning
        - 95% of limit → error/critical

        Args:
            telemetry: Current motor telemetry data.
            motor_info: MotorModelInfo with limits definition.

        Returns:
            ProtectionStatus with status and violations list.
        """
        if motor_info is None or not motor_info.limits:
            return ProtectionStatus(status="ok")

        violations: list[ProtectionViolation] = []
        max_status = "ok"

        # Check temperature limits
        if MotorLimit.LIMIT_TEMPERATURE_MAX_C in motor_info.limits and telemetry.temperature is not None:
            temp_limit_obj = motor_info.limits[MotorLimit.LIMIT_TEMPERATURE_MAX_C]
            temp_max = temp_limit_obj.value
            current_temp = float(telemetry.temperature)

            if current_temp > temp_max * 0.95:
                max_status = "critical"
                violations.append(
                    ProtectionViolation(
                        type="temperature_critical",
                        value=current_temp,
                        limit=temp_max,
                    )
                )
                logger.warning(f"Motor {telemetry.id}: temperature CRITICAL {current_temp}°C / {temp_max}°C")
            elif current_temp > temp_max * 0.85:
                if max_status != "critical":
                    max_status = "warning"
                violations.append(
                    ProtectionViolation(
                        type="temperature_warning",
                        value=current_temp,
                        limit=temp_max,
                    )
                )
                logger.warning(f"Motor {telemetry.id}: temperature WARNING {current_temp}°C / {temp_max}°C")

        # Check current limits
        if MotorLimit.LIMIT_CURRENT_MAX_MA in motor_info.limits and telemetry.current is not None:
            current_limit_obj = motor_info.limits[MotorLimit.LIMIT_CURRENT_MAX_MA]
            current_max = current_limit_obj.value
            current_value = float(telemetry.current)

            if current_value > current_max * 0.95:
                max_status = "critical"
                violations.append(
                    ProtectionViolation(
                        type="current_critical",
                        value=current_value,
                        limit=current_max,
                    )
                )
                logger.warning(f"Motor {telemetry.id}: current CRITICAL {current_value}mA / {current_max}mA")
            elif current_value > current_max * 0.85:
                if max_status != "critical":
                    max_status = "warning"
                violations.append(
                    ProtectionViolation(
                        type="current_warning",
                        value=current_value,
                        limit=current_max,
                    )
                )
                logger.warning(f"Motor {telemetry.id}: current WARNING {current_value}mA / {current_max}mA")

        # Check voltage limits
        if MotorLimit.LIMIT_VOLTAGE_MIN in motor_info.limits and telemetry.voltage is not None:
            voltage_min_obj = motor_info.limits[MotorLimit.LIMIT_VOLTAGE_MIN]
            voltage_min = voltage_min_obj.value
            current_voltage = telemetry.voltage

            if current_voltage < voltage_min * 1.05:  # Within 5% above minimum
                max_status = "critical"
                violations.append(
                    ProtectionViolation(
                        type="voltage_low_critical",
                        value=current_voltage,
                        limit=voltage_min,
                    )
                )
                logger.warning(f"Motor {telemetry.id}: voltage LOW CRITICAL {current_voltage}V / {voltage_min}V")
            elif current_voltage < voltage_min * 1.10:  # Within 10% above minimum
                if max_status != "critical":
                    max_status = "warning"
                violations.append(
                    ProtectionViolation(
                        type="voltage_low_warning",
                        value=current_voltage,
                        limit=voltage_min,
                    )
                )
                logger.warning(f"Motor {telemetry.id}: voltage LOW WARNING {current_voltage}V / {voltage_min}V")

        if MotorLimit.LIMIT_VOLTAGE_MAX in motor_info.limits and telemetry.voltage is not None:
            voltage_max_obj = motor_info.limits[MotorLimit.LIMIT_VOLTAGE_MAX]
            voltage_max = voltage_max_obj.value
            current_voltage = telemetry.voltage

            if current_voltage > voltage_max * 0.95:
                max_status = "critical"
                violations.append(
                    ProtectionViolation(
                        type="voltage_high_critical",
                        value=current_voltage,
                        limit=voltage_max,
                    )
                )
                logger.warning(f"Motor {telemetry.id}: voltage HIGH CRITICAL {current_voltage}V / {voltage_max}V")
            elif current_voltage > voltage_max * 0.85:
                if max_status != "critical":
                    max_status = "warning"
                violations.append(
                    ProtectionViolation(
                        type="voltage_high_warning",
                        value=current_voltage,
                        limit=voltage_max,
                    )
                )
                logger.warning(f"Motor {telemetry.id}: voltage HIGH WARNING {current_voltage}V / {voltage_max}V")

        return ProtectionStatus(status=max_status, violations=violations)

    async def start(
        self,
        callback: Callable | None = None,
        fps: int = 30,
    ) -> None:
        """Start motor data reading loop.

        Initializes motor buses, registers motors and calibrations, and starts
        async telemetry streaming.

        Args:
            callback: Optional async callable to invoke with each telemetry frame.
                     Signature: callback(frame: RobotTelemetryFrame) -> None
            fps: Target frames per second (default 30).

        Raises:
            OperationalError: If motorbus initialization or connection fails.
        """
        if self._running:
            logger.warning("RobotTelecontrolService already started")
            return

        self._running = True
        self._callback = callback
        self._target_fps = fps
        self._frame_interval = 1.0 / fps

        try:
            # Initialize motor buses
            for bus_name, conn in self._robot.motor_bus_connections.items():
                logger.info(f"Initializing motor bus: {bus_name}")

                # Create motor bus
                bus = MotorBus.create(
                    motorbus_type=conn.motor_bus_type,
                    interface=conn.interface,
                    baud_rate=conn.baudrate,
                )

                # Connect to bus
                bus.connect()
                logger.info(f"Connected to motor bus: {bus_name}")

                # Get motor IDs from robot definition
                motor_ids = self._get_motor_bus_motor_ids(bus_name)
                logger.debug(f"Motor bus '{bus_name}' has motors: {motor_ids}")

                # Scan and register motors
                if motor_ids:
                    bus.scan_motors()
                    # the motors have been registered during scan_motors
                    # for motor_id in motor_ids:
                    #     if motor_id in scanned:
                    #         motor_info = scanned[motor_id]
                    #         bus.register_motor(motor_id, motor_info)
                    #         logger.debug(f"Registered motor {motor_id} on bus {bus_name}")

                    # Merge custom protection limits from robot.custom_protection_settings
                    self._merge_custom_protection_limits(bus)

                # Register calibrations
                cal_list = self._robot.calibration_settings.get(bus_name, [])
                for cal in cal_list:
                    if cal.id is not None:
                        bus.register_calibration(cal.id, cal)
                        logger.debug(f"Registered calibration for motor {cal.id} on bus {bus_name}")

                self._motor_buses[bus_name] = bus

            # Start read loop task
            self._read_task = asyncio.create_task(self._read_loop())
            logger.info(f"Started RobotTelecontrolService with {len(self._motor_buses)} motor buses")

        except Exception as e:
            self._running = False
            # Clean up any partially initialized buses
            for bus in self._motor_buses.values():
                try:
                    bus.disconnect()
                except Exception:
                    pass
            self._motor_buses.clear()
            logger.error(f"Failed to start RobotTelecontrolService: {e}")
            raise OperationalError(
                i18n_key="hardware.robot_device.connect_failed",
                device_id=self._robot.id,
                retriable=False,
            ) from e

    async def stop(self) -> None:
        """Stop motor data reading loop and disconnect all buses.

        Cancels the read task and disconnects all motor buses.
        Captures and logs any non-CancelledError exceptions from the read task.
        """
        if not self._running:
            return

        self._running = False

        # Cancel read task and handle exceptions
        if self._read_task and not self._read_task.done():
            self._read_task.cancel()
            try:
                await self._read_task
            except asyncio.CancelledError:
                # Expected when cancelling task
                pass
            except Exception as e:
                # Capture and log any other exception from the task
                logger.error(f"Read task terminated with exception during stop: {type(e).__name__}: {e}", exc_info=True)

        # Disconnect all buses
        for bus_name, bus in self._motor_buses.items():
            try:
                bus.disconnect()
                logger.info(f"Disconnected from motor bus: {bus_name}")
            except Exception as e:
                logger.exception(f"Error disconnecting motor bus {bus_name}: {e}")

        self._motor_buses.clear()
        logger.info("Stopped RobotTelecontrolService")

    def _update_fps(self, current_time: float) -> None:
        """Update actual FPS calculation.

        Maintains a deque of timestamps (up to 2 seconds) and recalculates FPS
        when sufficient data is available. Updates once per second. FPS is
        rounded to nearest integer.

        Args:
            current_time: Current timestamp (seconds).
        """
        self._timestamp_deque.append(current_time)

        # Keep only ~2 seconds of history
        max_history = 2.0
        min_time = current_time - max_history
        while self._timestamp_deque and self._timestamp_deque[0] < min_time:
            self._timestamp_deque.popleft()

        # Recalculate FPS if we have enough samples (>= 2 * fps)
        min_samples = max(2, int(2 * self._target_fps))
        if len(self._timestamp_deque) >= min_samples:
            oldest_time = self._timestamp_deque[0]
            time_diff = current_time - oldest_time
            if time_diff > 0:
                fps_float = (len(self._timestamp_deque) - 1) / time_diff
                self._actual_fps = round(fps_float)  # Round to nearest integer
                logger.debug(f"Updated FPS: {self._actual_fps} (samples: {len(self._timestamp_deque)})")

            # Remove samples older than 1 second to prepare for next calculation
            prune_time = current_time - 1.0
            while self._timestamp_deque and self._timestamp_deque[0] < prune_time:
                self._timestamp_deque.popleft()

    def _is_fatal_error(self, exception: Exception) -> bool:
        """Determine if an exception is fatal and requires service termination.

        Fatal errors include:
        - SystemError, SystemExit: Critical system failures
        - MemoryError: Out of memory
        - KeyboardInterrupt: User requested termination
        - ImportError, AttributeError: Code/driver integrity issues

        Transient (non-fatal) errors:
        - IOError, OSError: Temporary I/O issues
        - TimeoutError: Network/bus timeouts
        - RuntimeError, ValueError: May be transient driver issues

        Args:
            exception: The exception to evaluate.

        Returns:
            True if fatal, False if potentially transient.
        """
        # System-level fatal errors
        if isinstance(exception, (SystemError, SystemExit, MemoryError, KeyboardInterrupt)):
            return True

        # Code integrity issues (should never happen in production)
        if isinstance(exception, (ImportError, AttributeError, TypeError)):
            # TypeError could indicate driver API signature mismatch
            return True

        # All other errors (IOError, RuntimeError, ValueError, etc.) are considered transient
        return False

    def _build_telemetry_frame(
        self,
        bus_results: list,
        current_time: float,
    ) -> RobotTelemetryFrame:
        """Build telemetry frame from bus read results.

        Args:
            bus_results: Results from asyncio.gather on bus read operations.
            current_time: Current timestamp.

        Returns:
            RobotTelemetryFrame with motor data from all buses.
        """
        motor_buses_data = {}

        for (bus_name, bus), result in zip(self._motor_buses.items(), bus_results, strict=True):
            if isinstance(result, Exception):
                continue
            if isinstance(result, dict):
                # Map motor_id keys to motor names based on robot definition
                motors_by_name = {}
                if isinstance(self._robot.definition, RobotDefinition):
                    bus_def = self._robot.definition.motor_buses.get(bus_name)
                    if bus_def:
                        # Create mapping from motor_id to motor name
                        id_to_name = {}
                        for motor_name, motor_def in bus_def.motors.items():
                            motor_id = motor_def.id
                            # For tuples, use first element
                            if isinstance(motor_id, tuple):
                                motor_id = motor_id[0]
                            id_to_name[motor_id] = motor_name
                        # Rename keys in result and calculate protection_status
                        for motor_id, telemetry in result.items():
                            motor_name = id_to_name.get(motor_id)
                            if motor_name:
                                # Calculate protection status based on motor limits
                                motor_info = bus.motors.get(motor_id)
                                protection_status = self._calculate_protection_status(telemetry, motor_info)
                                telemetry.protection_status = protection_status
                                motors_by_name[motor_name] = telemetry

                motor_buses_data[bus_name] = MotorBusData(
                    bus_name=bus_name,
                    motors=motors_by_name,
                )

        # Update FPS tracking
        self._update_fps(current_time)

        # Create and return frame
        return RobotTelemetryFrame(
            timestamp=current_time,
            motor_buses=motor_buses_data,
            actual_fps=self._actual_fps,
            normalized=self._normalized,
        )

    async def _read_loop(self) -> None:
        """Main async loop for reading motor telemetry.

        Reads from all motor buses concurrently, respects polling state,
        and invokes callback with each frame.

        Features robust exception handling:
        - Transient driver errors are logged and retried
        - Fatal exceptions terminate the loop gracefully with logging
        - Callbacks are isolated (sync callbacks run in thread pool)
        - Callback exceptions are caught and logged without killing loop
        """
        logger.info("Started motor telemetry read loop")
        last_read_time = time.time()

        try:
            while self._running:
                # Wait if polling is disabled
                await self._polling_event.wait()

                # Calculate sleep time to maintain target FPS
                current_time = time.time()
                elapsed = current_time - last_read_time
                sleep_time = max(0, self._frame_interval - elapsed)

                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)

                if not self._running:
                    break

                # Read all motor buses concurrently (with exception handling)
                try:
                    current_time = time.time()
                    read_tasks = [
                        bus.bulk_read_telemetry(list(bus.motors.keys())) for bus in self._motor_buses.values()
                    ]

                    bus_results = await asyncio.gather(*read_tasks, return_exceptions=True)

                    # Check for fatal errors and update error counter
                    has_error = False
                    for (bus_name, _), result in zip(self._motor_buses.items(), bus_results, strict=True):
                        if isinstance(result, Exception):
                            has_error = True
                            if self._is_fatal_error(result):
                                # Fatal error from a bus - stop immediately
                                logger.critical(
                                    f"Fatal error from bus {bus_name} (type: {type(result).__name__}): {result}. "
                                    f"Stopping service.",
                                    exc_info=result,
                                )
                                self._running = False
                                raise result  # Re-raise to exit the loop
                            # Non-fatal error - log and continue
                            logger.warning(f"Error reading bus {bus_name}: {result}")

                    # Update consecutive error counter
                    if has_error:
                        self._consecutive_errors += 1
                        # Check if exceeded threshold
                        if self._consecutive_errors >= self._max_consecutive_errors:
                            logger.critical(
                                f"Exceeded max consecutive errors ({self._max_consecutive_errors}). "
                                f"Stopping service to prevent silent failure.",
                                exc_info=False,
                            )
                            self._running = False
                            break
                    else:
                        # Success - reset counter
                        self._consecutive_errors = 0

                    # Build telemetry frame from results
                    frame = self._build_telemetry_frame(bus_results, current_time)

                    # Invoke callback if provided (with exception isolation)
                    if self._callback:
                        try:
                            if asyncio.iscoroutinefunction(self._callback):
                                await self._callback(frame)
                            else:
                                # Run sync callback in thread pool to avoid blocking event loop
                                loop = asyncio.get_running_loop()
                                await loop.run_in_executor(None, self._callback, frame)
                        except Exception as e:
                            logger.warning(
                                f"Callback error (non-fatal, continuing loop): {type(e).__name__}: {e}", exc_info=True
                            )

                    last_read_time = time.time()

                except asyncio.CancelledError:
                    # Graceful shutdown requested
                    break
                except Exception as e:
                    # Increment error counter
                    self._consecutive_errors += 1

                    # Check if this is a fatal error or too many consecutive failures
                    is_fatal = self._is_fatal_error(e)
                    exceeds_threshold = self._consecutive_errors >= self._max_consecutive_errors

                    if is_fatal:
                        logger.critical(
                            f"Fatal error in read loop (type: {type(e).__name__}): {e}. Stopping service.",
                            exc_info=True,
                        )
                        self._running = False
                        break
                    elif exceeds_threshold:
                        logger.critical(
                            f"Exceeded max consecutive errors ({self._max_consecutive_errors}). "
                            f"Last error: {type(e).__name__}: {e}. Stopping service to prevent silent failure.",
                            exc_info=True,
                        )
                        self._running = False
                        break
                    else:
                        # Transient error - log and retry
                        logger.error(
                            f"Error in read loop ({self._consecutive_errors}/{self._max_consecutive_errors}):",
                            f"{type(e).__name__}: {e}",
                            exc_info=True,
                        )
                        await asyncio.sleep(_ERROR_RETRY_DELAY_SECONDS)

        except asyncio.CancelledError:
            # Expected cancellation from stop()
            logger.debug("Read loop cancelled")
        except Exception as e:
            # Fatal exception - log critical error and terminate
            logger.critical(f"Fatal exception in read loop, terminating: {type(e).__name__}: {e}", exc_info=True)
            self._running = False
        finally:
            logger.info("Exited motor telemetry read loop")

    async def emergency_stop(self) -> None:
        """Disable all motors immediately (set torque to off).

        Concurrently disables all motors on all buses.
        """
        logger.warning("Emergency stop initiated")
        tasks = []
        for bus in self._motor_buses.values():
            for motor_id in bus.motors.keys():
                tasks.append(asyncio.create_task(self._disable_motor(bus, motor_id)))

        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for result in results:
                if isinstance(result, Exception):
                    logger.error(f"Error disabling motor: {result}")

    async def _disable_motor(self, bus: MotorBus, motor_id: MotorID) -> None:
        """Helper to disable a single motor."""
        try:
            bus.set_torque(motor_id, False)
        except Exception as e:
            logger.error(f"Failed to disable motor {motor_id}: {e}")

    def _clamp_position(self, bus_name: str, motor_name: str, position: float) -> tuple[float, bool]:
        """Clamp position to calibration range and return original/clamped state.

        Args:
            bus_name: Motor bus name.
            motor_name: Motor logical name.
            position: Requested position value.

        Returns:
            Tuple of (clamped_position, was_clamped).
        """
        cal_list = self._robot.calibration_settings.get(bus_name, [])
        for cal in cal_list:
            if cal.name == motor_name:
                range_min = float(cal.range_min)
                range_max = float(cal.range_max)

                if position < range_min or position > range_max:
                    clamped = max(range_min, min(range_max, position))
                    logger.info(
                        f"Position clamped for {bus_name}.{motor_name}: {position} → {clamped} "
                        f"(range: [{range_min}, {range_max}])"
                    )
                    return clamped, True
                return position, False

        # No calibration found, return original
        return position, False

    async def set_positions(self, motor_positions: dict[str, dict[str, float]]) -> dict[str, list[str]]:
        """Set target positions for multiple motors with clamping and feedback.

        Args:
            motor_positions: Mapping from bus_name to {motor_name: position}.
                            Motor names are logical names from robot definition.
                            If normalized, values are [-1, 1]; else raw encoder units.

        Returns:
            Dictionary mapping bus_name to list of motor_names that were clamped.
        """
        tasks = []
        clamped_motors: dict[str, list[str]] = {}

        for bus_name, motors_dict in motor_positions.items():
            bus = self._motor_buses.get(bus_name)
            if not bus:
                logger.warning(f"Motor bus '{bus_name}' not found")
                continue

            clamped_motors[bus_name] = []

            # Convert motor names to motor IDs
            motor_id_positions = await self._names_to_ids(bus_name, motors_dict.keys())

            for motor_name, position in motors_dict.items():
                motor_id = motor_id_positions.get(motor_name)
                if motor_id is not None:
                    # Clamp position to calibration range
                    clamped_position, was_clamped = self._clamp_position(bus_name, motor_name, position)
                    if was_clamped:
                        clamped_motors[bus_name].append(f"{motor_name} ({position:.2f}→{clamped_position:.2f})")

                    tasks.append(asyncio.create_task(self._set_motor_position(bus, motor_id, clamped_position)))

        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for result in results:
                if isinstance(result, Exception):
                    logger.error(f"Error setting position: {result}")

        return clamped_motors

    async def _set_motor_position(self, bus: MotorBus, motor_id: MotorID, position: float) -> None:
        """Helper to set position for a single motor."""
        try:
            position_type = PositionType.NORMALIZED if self._normalized else PositionType.RAW
            bus.set_position(motor_id, position, position_type=position_type)
        except Exception as e:
            logger.error(f"Failed to set position for motor {motor_id}: {e}")

    async def set_torques(self, motor_enabled: dict[str, dict[str, bool]]) -> None:
        """Enable/disable torque for multiple motors.

        Args:
            motor_enabled: Mapping from bus_name to {motor_name: enabled state}.
                          Motor names are logical names from robot definition.
        """
        tasks = []

        for bus_name, motors_dict in motor_enabled.items():
            bus = self._motor_buses.get(bus_name)
            if not bus:
                logger.warning(f"Motor bus '{bus_name}' not found")
                continue

            # Convert motor names to motor IDs
            motor_id_enabled = await self._names_to_ids(bus_name, motors_dict.keys())

            for motor_name, enabled in motors_dict.items():
                motor_id = motor_id_enabled.get(motor_name)
                if motor_id is not None:
                    tasks.append(asyncio.create_task(self._set_motor_torque(bus, motor_id, enabled)))

        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for result in results:
                if isinstance(result, Exception):
                    logger.error(f"Error setting torque: {result}")

    async def _set_motor_torque(self, bus: MotorBus, motor_id: MotorID, enabled: bool) -> None:
        """Helper to set torque for a single motor."""
        try:
            bus.set_torque(motor_id, enabled)
        except Exception as e:
            logger.error(f"Failed to set torque for motor {motor_id}: {e}")

    async def set_velocities(self, motor_velocities: dict[str, dict[str, float]]) -> dict[str, list[str]]:
        """Set target velocities for multiple motors with validation and feedback.

        Args:
            motor_velocities: Mapping from bus_name to {motor_name: velocity}.
                             Motor names are logical names from robot definition.

        Returns:
            Dictionary mapping bus_name to list of motor_names that were validated/modified.
        """
        tasks = []
        validated_motors: dict[str, list[str]] = {}

        for bus_name, motors_dict in motor_velocities.items():
            bus = self._motor_buses.get(bus_name)
            if not bus:
                logger.warning(f"Motor bus '{bus_name}' not found")
                continue

            validated_motors[bus_name] = []

            # Convert motor names to motor IDs
            motor_id_velocities = await self._names_to_ids(bus_name, motors_dict.keys())

            for motor_name, velocity in motors_dict.items():
                motor_id = motor_id_velocities.get(motor_name)
                if motor_id is not None:
                    # Check velocity against motor limits
                    validated_velocity, validation_notes = self._validate_velocity(bus, motor_id, motor_name, velocity)
                    if validation_notes:
                        validated_motors[bus_name].append(f"{motor_name}: {validation_notes}")

                    # Delegate to MotorBus.set_velocity in a thread to avoid blocking the event loop
                    tasks.append(asyncio.create_task(asyncio.to_thread(bus.set_velocity, motor_id, validated_velocity)))

        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for result in results:
                if isinstance(result, Exception):
                    logger.error(f"Error setting velocity: {result}")

        return validated_motors

    def _validate_velocity(
        self,
        bus: MotorBus,
        motor_id: MotorID,
        motor_name: str,
        velocity: float,
    ) -> tuple[float, str]:
        """Validate and optionally clamp velocity against motor limits.

        Args:
            bus: MotorBus instance.
            motor_id: Motor ID on the bus.
            motor_name: Motor logical name (for logging).
            velocity: Requested velocity value.

        Returns:
            Tuple of (validated_velocity, validation_notes_string).
        """
        motor_info = bus.motors.get(motor_id)
        if not motor_info or not motor_info.limits:
            return velocity, ""

        notes = ""
        final_velocity = velocity

        # Check against current limit if available
        if MotorLimit.LIMIT_CURRENT_MAX_MA in motor_info.limits:
            current_limit_obj = motor_info.limits[MotorLimit.LIMIT_CURRENT_MAX_MA]
            current_max = current_limit_obj.value
            # Assume velocity is proportional to current; warn if high velocity with current limit
            if abs(velocity) > _HIGH_VELOCITY_WARNING_THRESHOLD:
                notes += f"high velocity ({velocity:.2f}) near current limit ({current_max}mA); "
                logger.warning(f"Motor {motor_name} velocity {velocity:.2f} is high (current limit: {current_max}mA)")

        # Log validation result
        if notes:
            logger.info(f"Velocity validation for {motor_name}: {notes}")

        return final_velocity, notes

    async def polling(self, enabled: bool) -> None:
        """Pause/resume motor data polling.

        Args:
            enabled: True to enable polling, False to pause.
        """
        if enabled:
            self._polling_event.set()
            logger.info("Motor polling enabled")
        else:
            self._polling_event.clear()
            logger.info("Motor polling disabled")

    def _calculate_homing_offset(self, current_position: int, motor_info: MotorModelInfo) -> int:
        """Calculate homing offset based on current position and motor resolution.

        Algorithm from lerobot:
        - half_turn = int((resolution - 1) / 2)
        - homing_offset = int(max_res / 2) - current_position
        - where max_res = resolution - 1

        Args:
            current_position: Current raw position from motor.
            motor_info: MotorModelInfo with encoder_resolution.

        Returns:
            Calculated homing_offset.
        """
        resolution = motor_info.encoder_resolution
        max_res = resolution - 1
        half_turn = int((resolution - 1) / 2)
        homing_offset = int(max_res / 2) - current_position

        logger.debug(
            f"Homing offset calculation: resolution={resolution}, max_res={max_res}, "
            f"half_turn={half_turn}, current_pos={current_position}, homing_offset={homing_offset}"
        )

        return homing_offset

    async def set_homing_offsets(self) -> int:
        """Calculate and set homing offsets for all motors across all motor buses.

        For each motor calibration on each bus: resets offset/range → reads current position
        → calculates homing offset → updates and registers calibration on the bus.

        Pauses polling during calibration update.

        Returns:
            Total number of motors processed.
        """
        # Pause polling during calibration
        await self.polling(False)
        total = 0
        self._robot.is_calibrated = False
        robot_manager = get_robot_manager()
        robot_manager.update_robot(self._robot)  # persist is_calibrated change

        try:
            for bus_name, bus in self._motor_buses.items():
                # Get calibration list for this bus
                motor_bus_def = self._robot.definition.motor_buses.get(bus_name)
                cal_list = self._robot.calibration_settings.get(bus_name, [])
                if not cal_list:
                    cal_list = [
                        MotorCalibration(
                            id=m.id,
                            name=m.name,
                            drive_mode=m.drive_mode,
                            range_min=0,
                            range_max=m.encoder_resolution - 1,
                            homing_offset=0,
                        )
                        for m in motor_bus_def.motors.values()
                    ]
                    self._robot.calibration_settings[bus_name] = cal_list
                    for cal in cal_list:
                        bus.register_calibration(cal.id, cal)

                for cal in cal_list:
                    motor_id = cal.id

                    motor_info = bus.motors.get(motor_id)

                    # Step 1: Reset offset and range to defaults
                    resolution = motor_info.encoder_resolution
                    max_res = resolution - 1

                    cal.homing_offset = 0  # Reset existing homing offsets
                    cal.range_min = 0
                    cal.range_max = max_res

                    logger.debug(
                        f"Reset calibration for motor {motor_id} on {bus_name}: offset=0, range=[0, {max_res}]"
                    )

                    # Step 2: Read current position (raw units)
                    telemetry = bus.read_telemetry(motor_id)
                    current_position = int(telemetry.raw_position)
                    logger.debug(f"Read current position for motor {motor_id} on {bus_name}: {current_position}")

                    # Step 3: Calculate homing offset based on current position
                    homing_offset = self._calculate_homing_offset(current_position, motor_info)

                    # Step 4: Update calibration with calculated homing offset
                    cal.homing_offset = homing_offset
                    # Register updated calibration with bus (motorbus uses same calibration object)
                    bus.register_calibration(motor_id, cal)

                    logger.info(
                        f"Set homing offset for motor {motor_id} on {bus_name}: "
                        f"reset → read position {current_position} → "
                        f"calculated homing_offset={homing_offset}, range=[0, {max_res}]"
                    )

                    total += 1

        finally:
            # Resume polling
            await self.polling(True)

        return total

    async def set_ranges(self, motor_ranges: dict[str, dict[str, dict[str, int]]]) -> None:
        """Set position ranges for motors.

        Pauses polling during calibration update. Need to call set_homing_offsets first.

        Args:
            motor_ranges: Mapping from bus_name to {motor_name: {range_min, range_max}}.
                         Motor names are logical names from robot definition.
        """
        # Pause polling during calibration
        await self.polling(False)

        try:
            for bus_name, motors_dict in motor_ranges.items():
                bus = self._motor_buses.get(bus_name)
                assert bus is not None, f"Motor bus '{bus_name}' not found"
                motor_bus_def = self._robot.definition.motor_buses.get(bus_name)
                cal_list = self._robot.calibration_settings.get(bus_name)
                for cal in cal_list:
                    robot_motor_info = motor_bus_def.motors.get(cal.name)
                    if not robot_motor_info.is_full_turn:
                        # no range setting for full turn motors

                        motor_name = cal.name
                        range_value = motors_dict.get(motor_name)
                        range_min = range_value.get("range_min")
                        range_max = range_value.get("range_max")
                        cal.range_min = range_min
                        cal.range_max = range_max

                    bus.write_range(cal.id, range_min, range_max)

            self._robot.is_calibrated = True
            robot_manager = get_robot_manager()
            robot_manager.update_robot(self._robot.id)  # persist is_calibrated change

        finally:
            # Resume polling
            await self.polling(True)
