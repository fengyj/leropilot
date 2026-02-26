"""MotorBus base class providing unified motor control interface.

MotorBus provides a unified interface for motor control operations, following the
lerobot-inspired architecture where different MotorBus subclasses handle different
communication protocols and use appropriate drivers directly.
"""

import logging
import math
import threading
from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Generic

from leropilot.exceptions import OperationalError, ValidationError
from leropilot.models.hardware import (
    MotorBusDefinition,
    MotorCalibration,
    MotorID,
    MotorModelInfo,
    MotorNormMode,
    MotorTelemetry,
    PositionType,
    UnitType,
)

from ..motor_drivers.base import BaseMotorDriver, MotorIDVar

# Do not redefine MotorIDVar here; use the typevar from the driver base

logger = logging.getLogger(__name__)


class PositionConvertCache(Generic[MotorIDVar]):
    """Per-MotorBus cached position converter factory for position conversions.

    Stores callables keyed by (motor_id, from_type, to_type). Each converter
    is built once and captures the motor's calibration/model constants so
    repeated calls to the converter are fast and allocation-free.
    """

    def __init__(self, motorbus: "MotorBus[MotorIDVar]") -> None:
        self._motorbus = motorbus
        # Position converters keyed by (motor_id, PositionType, PositionType)
        self._cache: dict[tuple[MotorIDVar, PositionType, PositionType], Callable[[float], float]] = {}

    def convert(self, motor_id: MotorIDVar, from_type: PositionType, to_type: PositionType, value: float) -> float:
        """Convert a value from `from_type` to `to_type` for the given motor.

        This will build and cache the per-(motor_id, from, to) converter on first use
        and call it immediately. Converters raise `ValueError` when conversion is
        not possible (missing calibration or invalid constants).
        """
        # Identity conversion is a no-op
        if from_type == to_type:
            return value

        key = (motor_id, from_type, to_type)
        conv = self._cache.get(key)
        if conv is None:
            conv = self._build_converter(motor_id, from_type, to_type)
            if conv is None:
                raise ValueError(f"Unsupported conversion: {from_type} -> {to_type} for motor {motor_id}")
            self._cache[key] = conv
        result = conv(value)
        # Converters are expected to raise on failure; guard double-check
        return result

    def _build_converter(
        self,
        motor_id: MotorIDVar,
        from_type: PositionType,
        to_type: PositionType,
    ) -> Callable[[float], float] | None:
        mb = self._motorbus
        cal = mb.calibrations[motor_id]
        model_info = mb.motors[motor_id]

        # Capture commonly used constants
        homing_offset = cal.homing_offset if cal else 0.0
        soft_homing = bool(cal.soft_homing_offset) if cal else False
        min_ = cal.range_min if cal else 0.0
        max_ = cal.range_max if cal else 0.0
        denom = max_ - min_
        drive_mode = int(cal.drive_mode) if cal else 0
        norm_mode = cal.norm_mode if cal else None
        # Directly read model attributes; missing attributes are programming errors and should raise
        pos_ratio = model_info.position_to_radian_ratio
        encoder_res = model_info.encoder_resolution

        # Helper builders
        def raw_to_cal(x: float) -> float:
            return x - homing_offset if soft_homing else x

        def raw_to_norm(x: float) -> float:
            # RAW -> NORMALIZED delegates to RAW -> CALIBRATED then CALIBRATED -> NORMALIZED
            cal_val = raw_to_cal(x)
            return cal_to_norm(cal_val)

        def raw_to_raw_in_radian(x: float) -> float:
            return x * pos_ratio

        def raw_to_cal_radian(x: float) -> float:
            return raw_to_raw_in_radian(raw_to_cal(x))

        def cal_to_raw(x: float) -> float:
            return x + homing_offset if soft_homing else x

        def cal_to_norm(x: float) -> float:
            # CALIBRATED -> NORMALIZED requires calibration
            if denom == 0.0:
                raise ValueError(f"Invalid calibration range for motor {motor_id}")
            if norm_mode is None:
                raise ValueError(f"Missing norm_mode for motor {motor_id}")
            bounded = min(max_, max(min_, x))
            if norm_mode == MotorNormMode.RANGE_M100_100:
                norm = (((bounded - min_) / denom) * 200.0) - 100.0
                return -norm if drive_mode == 1 else norm
            if norm_mode == MotorNormMode.RANGE_0_100:
                norm = ((bounded - min_) / denom) * 100.0
                return 100.0 - norm if drive_mode == 1 else norm
            if norm_mode == MotorNormMode.DEGREES:
                mid = (min_ + max_) / 2.0
                max_res = (encoder_res - 1.0) if encoder_res else denom
                if max_res == 0.0:
                    raise ValueError(f"Invalid encoder resolution for motor {motor_id}")
                return (x - mid) * 360.0 / max_res
            raise NotImplementedError(f"Unsupported MotorNormMode: {norm_mode}")

        def cal_to_raw_in_radian(x: float) -> float:
            return raw_to_raw_in_radian(cal_to_raw(x))

        def norm_to_raw(x: float) -> float:
            # NORMALIZED -> RAW requires calibration
            if denom == 0.0:
                raise ValueError(f"Invalid calibration range for motor {motor_id}")
            if norm_mode is None:
                raise ValueError(f"Missing norm_mode for motor {motor_id}")
            # normalized (-1..1) -> calibrated
            if norm_mode == MotorNormMode.RANGE_M100_100:
                percent = x * 100.0
                if drive_mode == 1:
                    percent = -percent
                calibrated = ((percent + 100.0) / 200.0) * denom + min_
            elif norm_mode == MotorNormMode.RANGE_0_100:
                percent = (x + 1.0) * 50.0
                if drive_mode == 1:
                    percent = 100.0 - percent
                calibrated = (percent / 100.0) * denom + min_
            elif norm_mode == MotorNormMode.DEGREES:
                deg = x * 180.0
                mid = (min_ + max_) / 2.0
                denom_res = (encoder_res - 1.0) if encoder_res else denom
                if denom_res == 0.0:
                    raise ValueError(f"Invalid encoder resolution for motor {motor_id}")
                calibrated = deg * denom_res / 360.0 + mid
            else:
                raise NotImplementedError(f"Unsupported MotorNormMode: {norm_mode}")
            return calibrated + homing_offset if soft_homing else calibrated

        def calibrated_in_radian_to_raw(x: float) -> float:
            raw_from_radian = x / pos_ratio
            return raw_from_radian + homing_offset if soft_homing else raw_from_radian

        def raw_to_raw_in_degree(x: float) -> float:
            return x * pos_ratio * (180.0 / math.pi)

        # Build mapping of supported converters
        mapping: dict[tuple[PositionType, PositionType], Callable[[float], float]] = {
            (PositionType.RAW, PositionType.CALIBRATED): raw_to_cal,
            (PositionType.RAW, PositionType.NORMALIZED): raw_to_norm,
            (PositionType.RAW, PositionType.RAW_IN_RADIAN): raw_to_raw_in_radian,
            (PositionType.RAW, PositionType.CALIBRATED_IN_RADIAN): raw_to_cal_radian,
            (PositionType.RAW, PositionType.RAW_IN_DEGREE): raw_to_raw_in_degree,
            (PositionType.CALIBRATED, PositionType.RAW): cal_to_raw,
            (PositionType.CALIBRATED, PositionType.NORMALIZED): cal_to_norm,
            (PositionType.CALIBRATED, PositionType.RAW_IN_RADIAN): cal_to_raw_in_radian,
            (PositionType.NORMALIZED, PositionType.RAW): norm_to_raw,
            (PositionType.RAW_IN_RADIAN, PositionType.RAW): (lambda x: x / pos_ratio),
            (PositionType.RAW_IN_DEGREE, PositionType.RAW): (lambda x: x * math.pi / (180.0 * pos_ratio)),
            (PositionType.CALIBRATED_IN_RADIAN, PositionType.RAW): calibrated_in_radian_to_raw,
        }

        # Direct mapping
        if (from_type, to_type) in mapping:
            return mapping[(from_type, to_type)]

        # Route via RAW: try to get from -> RAW and RAW -> to
        to_raw = mapping.get((from_type, PositionType.RAW))
        raw_to_target = mapping.get((PositionType.RAW, to_type))
        if to_raw and raw_to_target:

            def routed(x: float) -> float:
                # to_raw and raw_to_target are expected to raise ValueError when conversion
                # is not possible. We propagate that exception to the caller.
                r = to_raw(x)
                return raw_to_target(r)

            return routed

        # Unsupported
        return None


class VelocityConverterCache(Generic[MotorIDVar]):
    """Per-Motor cached velocity converters for raw <-> rad/s conversions.

    Stores a pair of callables keyed by motor_id: (raw_to_rad, rad_to_raw). Each
    callable captures the motor's `velocity_ratio` at build time for fast repeated
    conversions.
    """

    def __init__(self, motorbus: "MotorBus[MotorIDVar]") -> None:
        self._motorbus = motorbus
        self._cache: dict[MotorIDVar, tuple[Callable[[float], float], Callable[[float], float]]] = {}

    def raw_to_rad(self, motor_id: MotorIDVar, raw_v: float) -> float:
        """Convert a raw velocity to rad/s for the given motor ID."""
        if motor_id not in self._cache:
            raw_to_rad, rad_to_raw = self._build_converters(motor_id)
            self._cache[motor_id] = (raw_to_rad, rad_to_raw)
        return self._cache[motor_id][0](raw_v)

    def rad_to_raw(self, motor_id: MotorIDVar, rad_v: float) -> float:
        """Convert a rad/s velocity to raw units for the given motor ID."""
        if motor_id not in self._cache:
            raw_to_rad, rad_to_raw = self._build_converters(motor_id)
            self._cache[motor_id] = (raw_to_rad, rad_to_raw)
        return self._cache[motor_id][1](rad_v)

    def _build_converters(self, motor_id: MotorIDVar) -> tuple[Callable[[float], float], Callable[[float], float]]:
        mb = self._motorbus
        model_info = mb.motors.get(motor_id)
        assert model_info is not None, f"MotorModelInfo must be available for motor_id {motor_id} to build velocity converters"
        # Assume model_info and its velocity_ratio attribute exist; let AttributeError surface if not
        velocity_ratio = model_info.velocity_ratio
        # Read calibration drive_mode to determine direction inversion (0 = normal, 1 = inverted)
        cal = mb.calibrations.get(motor_id)
        drive_mode = int(cal.drive_mode) if cal else 0

        def raw_to_rad(v: float) -> float:
            val = v * velocity_ratio
            return -val if drive_mode == 1 else val

        def rad_to_raw(v: float) -> float:
            if velocity_ratio == 0:
                return 0.0
            raw = v / velocity_ratio
            return -raw if drive_mode == 1 else raw

        return raw_to_rad, rad_to_raw


class MotorBus(ABC, Generic[MotorIDVar]):
    """Abstract base class for motor bus implementations.

    MotorBus provides a unified interface for motor control operations.
    Different subclasses handle different communication protocols (serial, CAN, etc.)
    and use appropriate driver implementations directly.

    Thread Safety:
        MotorBus instances include an internal RLock to ensure that concurrent
        calls to the shared driver do not interleave bus transactions.

        All public methods that access the driver are wrapped in this lock.
    """

    def __init__(self) -> None:
        """Initialize MotorBus.

        Interface and baud rate are provided to :meth:`connect` when establishing
        a physical connection, not at construction time. This allows creating an
        offline bus instance (e.g., for calibration unit conversion) without any
        hardware-specific parameters.
        """
        self.interface: str | None = None
        self.baud_rate: int | None = None
        # Shared driver instance for all motors on this bus
        self.driver: BaseMotorDriver[MotorIDVar] | None = None
        # Map motor_id -> MotorModelInfo (driver is shared). MotorModelInfo is required
        # at registration time — callers should register with a full MotorModelInfo.
        self.motors: dict[MotorIDVar, MotorModelInfo] = {}
        # Map motor_id -> MotorCalibration
        self.calibrations: dict[MotorIDVar, MotorCalibration] = {}
        self._connected = False
        self._lock = threading.RLock()
        # Position converter cache per MotorBus instance
        self._position_converter_cache = PositionConvertCache(self)
        # Velocity converter cache per MotorBus instance
        self._velocity_converter_cache = VelocityConverterCache(self)
        
    @abstractmethod
    def connect(self, interface: str, baud_rate: int | None = None) -> None:
        """Connect to the motor bus.

        Stores ``interface`` and ``baud_rate`` on ``self`` and establishes the
        physical connection. Subclasses must call ``super()`` or assign these
        attributes themselves before creating the driver.

        Args:
            interface: Communication interface (serial port, CAN interface, etc.)
            baud_rate: Communication baudrate/bitrate

        Raises:
            OperationalError: If connection fails.
        """

    @abstractmethod
    def disconnect(self) -> None:
        """Disconnect from the motor bus.

        Raises:
            OperationalError: If disconnection fails.
        """
        pass

    def is_connected(self) -> bool:
        """Check if bus is connected."""
        return self._connected

    @abstractmethod
    def scan_motors(self, id_range: list[int] | None = None) -> dict[MotorIDVar, MotorModelInfo]:
        """Scan bus for motors and return mapping motor_id -> MotorModelInfo."""
        pass

    def register_motor(
        self,
        motor_id: MotorIDVar,
        motor_info: MotorModelInfo,
    ) -> None:
        """Register a motor with the bus using an explicit motor_id and a required MotorModelInfo.

        MotorModelInfo MUST be provided at registration time. This simplifies runtime
        assumptions elsewhere in the codebase (e.g., bulk reads) by guaranteeing
        `self.motors[motor_id]` is a valid `MotorModelInfo`.
        """
        if motor_id is None:
            raise ValueError("motor_id must be provided when registering a motor")
        self.motors[motor_id] = motor_info.model_copy(deep=True)  # store a copy because needs to change the limits data

    def register_motors_from_definition(self, bus_def: MotorBusDefinition) -> None:
        """Register all motors from a MotorBusDefinition without requiring hardware.

        Looks up each motor's MotorModelInfo from the motor table by brand/model/variant
        and calls :meth:`register_motor`. Motors not found in the table are skipped with
        a warning. This is the preferred way to populate motor info for a known robot,
        avoiding a hardware scan.

        Args:
            bus_def: MotorBusDefinition whose motors should be registered.
        """
        from ..motor_drivers.base import MotorUtil

        for motor_name, motor_def in bus_def.motors.items():
            model_info = MotorUtil.find_motor(motor_def.brand, motor_def.model, motor_def.variant)
            if model_info is not None:
                self.register_motor(motor_def.id, model_info)
            else:
                logger.warning(
                    f"Motor '{motor_name}' ({motor_def.brand}/{motor_def.model}/{motor_def.variant})"
                    " not found in motor table; skipping registration"
                )

    def register_calibration(
        self,
        motor_id: MotorIDVar,
        calibration: MotorCalibration,
    ) -> None:
        """Register calibration data for a motor to enable normalization."""
        self.calibrations[motor_id] = calibration

    def register_calibrations_from_list(
        self,
        cal_list: list[MotorCalibration],
        name_to_id: dict[str, MotorID] | None = None,
    ) -> None:
        """Register calibrations from a list, resolving motor IDs by name when needed.

        Args:
            cal_list: List of MotorCalibration entries to register.
            name_to_id: Optional mapping from motor name to motor ID. Used to resolve
                entries where :attr:`MotorCalibration.id` is ``None``.
        """
        for cal in cal_list:
            motor_id: MotorID | None = cal.id
            if motor_id is None and name_to_id and cal.name in name_to_id:
                motor_id = name_to_id[cal.name]
            if motor_id is not None:
                self.register_calibration(motor_id, cal)

    def _ensure_driver(self) -> BaseMotorDriver[MotorIDVar]:
        """Ensure driver is available, raising exception if not.

        Returns:
            The shared driver instance.

        Raises:
            OperationalError: If bus is not connected or driver is not available.
        """
        if not self.driver:
            raise OperationalError(
                i18n_key="hardware.robot_device.connect_failed",
                retriable=False,
                interface=self.interface,
            )
        return self.driver

    def get_motor_info(self, motor_id: MotorIDVar) -> MotorModelInfo | None:
        """Return the MotorModelInfo object associated with a registered motor, if any."""
        return self.motors.get(motor_id)

    def convert_calibration_units(
        self,
        motor_id: MotorIDVar,
        target_type: PositionType = PositionType.RAW,
    ) -> MotorCalibration:
        """Return a calibration snapshot converted to the requested unit.

        Args:
            motor_id: Motor id whose calibration should be converted.
            target_type: Target PositionType for position fields (default: RAW).

        Returns:
            A copy of the motor calibration with homing_offset/range values converted.

        Raises:
            ValidationError: If motor_id is not registered or calibration is missing.
        """
        if motor_id not in self.motors:
            raise ValidationError(
                i18n_key="hardware.motor_device.not_registered",
                motor_id=str(motor_id),
            )
        cal = self.calibrations.get(motor_id)
        if cal is None:
            raise ValueError(f"Missing calibration for motor {motor_id}")

        if target_type == PositionType.RAW:
            return cal.model_copy()

        converted = cal.model_copy()
        converted.homing_offset = self._position_converter_cache.convert(
            motor_id, PositionType.RAW, target_type, cal.homing_offset
        )
        converted.range_min = self._position_converter_cache.convert(
            motor_id, PositionType.RAW, target_type, cal.range_min
        )
        converted.range_max = self._position_converter_cache.convert(
            motor_id, PositionType.RAW, target_type, cal.range_max
        )
        return converted

    def read_telemetry(self, motor_id: MotorIDVar, position_type: PositionType = PositionType.RAW) -> MotorTelemetry:
        """Read telemetry from a single motor.

        Converts position to the specified position_type (raw, calibrated, or normalized).

        Args:
            motor_id: The ID of the motor to read.
            position_type: The position unit/representation to return (default: RAW).

        Raises:
            OperationalError: If read fails or bus not connected.
            ValidationError: If motor_id is not registered.
        """
        if motor_id not in self.motors:
            raise ValidationError(
                i18n_key="hardware.motor_device.not_registered",
                motor_id=str(motor_id),
            )
        with self._lock:
            driver = self._ensure_driver()
            # motor_id must be registered and contain a MotorModelInfo per contract
            model_info = self.motors[motor_id]
            telemetry = driver.read_telemetry(motor_id, model_info)
            if telemetry is None:
                raise OperationalError(
                    i18n_key="hardware.motor_device.read_failed",
                    motor_id=str(motor_id),
                )

            # Convert velocity from raw hardware units to rad/s via cached converter
            telemetry.velocity = self._velocity_converter_cache.raw_to_rad(motor_id, telemetry.velocity)

            # Convert position based on requested position_type (identity handled by converter)
            if telemetry.position is not None:
                converted_pos = self._position_converter_cache.convert(
                    motor_id, PositionType.RAW, position_type, telemetry.position
                )
                telemetry.position = converted_pos
                telemetry.position_type = position_type

            # Convert goal_position if available
            if telemetry.goal_position is not None:
                converted_goal = self._position_converter_cache.convert(
                    motor_id, PositionType.RAW, position_type, telemetry.goal_position
                )
                telemetry.goal_position = converted_goal

            return telemetry

    def bulk_read_telemetry(
        self, motor_ids: list[MotorIDVar], position_type: PositionType = PositionType.RAW
    ) -> dict[MotorIDVar, MotorTelemetry]:
        """Read telemetry from multiple motors efficiently.

        Uses the driver's native bulk read implementation for optimal performance.
        For protocols that support it (e.g., Dynamixel), this is a single bus transaction.

        Converts position to the specified position_type (raw, calibrated, or normalized).

        Args:
            motor_ids: List of motor IDs.
            position_type: The position unit/representation to return (default: RAW).

        Returns:
            Dict mapping motor_id -> MotorTelemetry. Motors that failed to read will be
            omitted from the result. Caller should check result length against input.

        Raises:
            OperationalError: If bus is not connected.
        """
        with self._lock:
            if not self.driver:
                raise OperationalError(
                    i18n_key="hardware.robot_device.connect_failed",
                    retriable=False,
                    interface=self.interface,
                )

            # Build mapping motor_id -> MotorModelInfo for the requested motor_ids.
            # We assume callers only pass registered motor IDs (simpler, trust contract).
            if not motor_ids:
                return {}

            motors_map: dict[MotorIDVar, MotorModelInfo] = {mid: self.motors[mid] for mid in motor_ids}

            # Use driver's bulk read method (single transaction for supported protocols)
            results = self.driver.bulk_read_telemetry(motors_map)

            # Log warning if some motors failed, but don't raise
            if len(results) < len(motor_ids):
                missing = set(motor_ids) - set(results.keys())
                logger.warning(f"Bulk telemetry read: {len(missing)} motor(s) failed: {missing}")

            # Build all three position types for each motor and convert velocities
            for mid, telemetry in results.items():
                # Convert velocity from raw hardware units to rad/s via cached converter
                telemetry.velocity = self._velocity_converter_cache.raw_to_rad(mid, telemetry.velocity)

                # Convert position based on requested position_type (identity handled by converter)
                converted_pos = self._position_converter_cache.convert(
                    mid, PositionType.RAW, position_type, telemetry.position
                ) if telemetry.position is not None else None
                if converted_pos is not None:
                    telemetry.position = converted_pos
                    telemetry.position_type = position_type

                # Convert goal_position if available
                if telemetry.goal_position is not None:
                    converted_goal = self._position_converter_cache.convert(
                        mid, PositionType.RAW, position_type, telemetry.goal_position
                    )
                    telemetry.goal_position = converted_goal

            return results

    def set_torque(self, motor_id: MotorIDVar, enabled: bool) -> None:
        """Enable/disable motor torque.

        Raises:
            OperationalError: If operation fails or bus is not connected.
            ValidationError: If motor_id is not registered.
        """
        if motor_id not in self.motors:
            raise ValidationError(
                i18n_key="hardware.motor_device.not_registered",
                motor_id=str(motor_id),
            )
        with self._lock:
            driver = self._ensure_driver()
            driver.set_torque(motor_id, enabled)

    def bulk_set_torque(self, motor_ids: list[MotorIDVar], enabled: bool) -> None:
        """Set torque for multiple motors efficiently.

        For protocols that support bulk write, this is a single bus transaction.

        Returns:
            Dict mapping motor_id -> success (bool). Caller should check all values
            to determine if any operations failed.

        Raises:
            OperationalError: If bus is not connected.
        """
        with self._lock:
            driver = self._ensure_driver()

            # Filter to only registered motors
            valid_ids = [mid for mid in motor_ids if mid in self.motors]
            if not valid_ids:
                return

            driver.bulk_set_torque(valid_ids, enabled)

    def get_operation_mode(self, motor_id: MotorIDVar) -> int:
        """Get the operation mode of a motor, if supported by the driver.

        Returns:
            The operation mode as an integer, or None if not supported.
        """
        with self._lock:
            driver = self._ensure_driver()
            return driver.get_operation_mode(motor_id)

    def bulk_get_operation_mode(self, motor_ids: list[MotorIDVar]) -> dict[MotorIDVar, int]:
        """Get operation modes for multiple motors efficiently.

        Returns:
            Dict mapping motor_id -> operation mode (int) or None if not supported.
        """
        with self._lock:
            driver = self._ensure_driver()
            return driver.bulk_get_operation_mode(motor_ids)

    def set_operation_mode(self, motor_id: MotorIDVar, mode: int) -> None:
        """Set the operation mode of a motor, if supported by the driver.

        Raises:
            OperationalError: If operation fails or bus is not connected.
            ValidationError: If motor_id is not registered.
        """
        if motor_id not in self.motors:
            raise ValidationError(
                i18n_key="hardware.motor_device.not_registered",
                motor_id=str(motor_id),
            )
        with self._lock:
            driver = self._ensure_driver()
            success = driver.set_operation_mode(motor_id, mode)
            if not success:
                raise OperationalError(
                    i18n_key="hardware.motor_device.operation_failed",
                    motor_id=str(motor_id),
                    operation="set_operation_mode",
                )

    def bulk_set_operation_mode(self, motor_ids: list[MotorIDVar], mode: int) -> None:
        """Set operation modes for multiple motors efficiently.

        Returns:
            Dict mapping motor_id -> success (bool). Caller should check all values
            to determine if any operations failed.
        """
        with self._lock:
            driver = self._ensure_driver()

            # Filter to only registered motors
            valid_ids = [mid for mid in motor_ids if mid in self.motors]
            if not valid_ids:
                return

            driver.bulk_set_operation_mode(valid_ids, mode)

    def get_register_value(self, motor_id: MotorIDVar, address: int) -> float:
        """Get a raw register value from a motor.

        Raises:
            OperationalError: If operation fails or bus is not connected.
            ValidationError: If motor_id is not registered.
        """
        if motor_id not in self.motors:
            raise ValidationError(
                i18n_key="hardware.motor_device.not_registered",
                motor_id=str(motor_id),
            )
        with self._lock:
            driver = self._ensure_driver()
            return driver.read_register(motor_id, address)

    def set_register_value(self, motor_id: MotorIDVar, address: int, value: float) -> None:
        """Set a raw register value on a motor.

        Raises:
            OperationalError: If operation fails or bus is not connected.
            ValidationError: If motor_id is not registered.
        """
        if motor_id not in self.motors:
            raise ValidationError(
                i18n_key="hardware.motor_device.not_registered",
                motor_id=str(motor_id),
            )
        with self._lock:
            driver = self._ensure_driver()
            driver.write_register(motor_id, address, value)

    def bulk_get_register_values(self, motor_ids: list[MotorIDVar], address: int) -> dict[MotorIDVar, float]:
        """Get raw register values from multiple motors efficiently.

        Returns:
            Dict mapping motor_id -> register value (float).
        """
        with self._lock:
            driver = self._ensure_driver()

            # Filter to only registered motors
            valid_ids = [mid for mid in motor_ids if mid in self.motors]
            if not valid_ids:
                return {}

            return driver.bulk_read_registers(valid_ids, address)

    def bulk_set_register_values(self, motor_values: dict[MotorIDVar, float], address: int) -> None:
        """Set raw register values on multiple motors efficiently.

        Args:
            motor_values: Dict mapping motor_id -> value to set.
            address: Register address to write.

        Returns:
            Dict mapping motor_id -> success (bool). Caller should check all values
            to determine if any operations failed.
        """
        with self._lock:
            driver = self._ensure_driver()

            # Filter to only registered motors
            valid_values = {mid: val for mid, val in motor_values.items() if mid in self.motors}
            if not valid_values:
                return

            driver.bulk_write_registers(valid_values, address)

    def get_register_value_in_standard_unit(self, motor_id: MotorIDVar, motor_info: MotorModelInfo, address: int, unit: UnitType) -> float:
        """Get a register value converted to a standard unit.

        Raises:
            OperationalError: If operation fails or bus is not connected.
            ValidationError: If motor_id is not registered.
        """
        if motor_id not in self.motors:
            raise ValidationError(
                i18n_key="hardware.motor_device.not_registered",
                motor_id=str(motor_id),
            )
        with self._lock:
            driver = self._ensure_driver()
            return driver.read_register_in_standard_unit(motor_id, motor_info, address, unit)

    def set_register_value_in_standard_unit(self, motor_id: MotorIDVar, motor_info: MotorModelInfo, address: int, value: float, unit: UnitType) -> None:
        """Set a register value converted from a standard unit.

        Raises:
            OperationalError: If operation fails or bus is not connected.
            ValidationError: If motor_id is not registered.
        """
        if motor_id not in self.motors:
            raise ValidationError(
                i18n_key="hardware.motor_device.not_registered",
                motor_id=str(motor_id),
            )
        with self._lock:
            driver = self._ensure_driver()
            driver.write_register_in_standard_unit(motor_id, motor_info, address, value, unit)

    def bulk_get_register_values_in_standard_unit(self, motor_info_map: dict[MotorIDVar, MotorModelInfo], address: int, unit: UnitType) -> dict[MotorIDVar, float]:
        """Get register values from multiple motors converted to a standard unit.

        Returns:
            Dict mapping motor_id -> register value (float).
        """
        with self._lock:
            driver = self._ensure_driver()

            return driver.bulk_read_registers_in_standard_unit(motor_info_map, address, unit)

    def bulk_set_register_values_in_standard_unit(self, motor_values: dict[MotorIDVar, float], motor_info_map: dict[MotorIDVar, MotorModelInfo], address: int, unit: UnitType) -> None:
        """Set register values on multiple motors converted from a standard unit.

        Args:
            motor_values: Dict mapping motor_id -> value to set.
            motor_info_map: Dict mapping motor_id -> MotorModelInfo.
            address: Register address to write.
            unit: Standard unit of the values.
        Returns:
            None
        """
        with self._lock:
            driver = self._ensure_driver()

            driver.bulk_write_registers_in_standard_unit(motor_values, motor_info_map, address, unit)

    def get_position(
        self,
        motor_id: MotorIDVar,
        position_type: PositionType = PositionType.RAW,
    ) -> float:
        """Get the current position of a motor in the specified position type.

        Args:
            motor_id: The ID of the motor to read.
            position_type: The position unit/representation to return (default: RAW).
        Returns:
            The motor position in the requested position type.
        """
        assert self.driver is not None, "Driver must be available to get position"
        position = self.driver.get_position(motor_id=motor_id)
        position = self._position_converter_cache.convert(
            motor_id, PositionType.RAW, position_type, position
        )
        return position

    def bulk_get_positions(
        self,
        motor_ids: list[MotorIDVar],
        position_type: PositionType = PositionType.RAW,
    ) -> dict[MotorIDVar, float]:
        """Get the current positions of multiple motors in the specified position type.

        Args:
            motor_ids: List of motor IDs.
            position_type: The position unit/representation to return (default: RAW).
        Returns:
            Dict mapping motor_id -> position in the requested position type.
        """
        assert self.driver is not None, "Driver must be available to bulk get positions"
        raw_positions = self.driver.bulk_get_positions(motor_ids=motor_ids)
        converted_positions: dict[MotorIDVar, float] = {}
        for motor_id, position in raw_positions.items():
            converted_position = self._position_converter_cache.convert(
                motor_id, PositionType.RAW, position_type, position
            )
            converted_positions[motor_id] = converted_position
        return converted_positions

    def get_goal_position(
        self,
        motor_id: MotorIDVar,
        position_type: PositionType = PositionType.RAW,
    ) -> float | None:
        """Get the last set goal position of a motor in the specified position type.

        Args:
            motor_id: The ID of the motor to read.
            position_type: The position unit/representation to return (default: RAW).
        Returns:
            The last set goal position in the requested position type, or None if not set.
        """
        assert self.driver is not None, "Driver must be available to get goal position"
        goal_position = self.driver.get_goal_position(motor_id=motor_id)

        goal_position = self._position_converter_cache.convert(
            motor_id, PositionType.RAW, position_type, goal_position
        )
        return goal_position

    def set_goal_position(
        self,
        motor_id: MotorIDVar,
        position: float,
        position_type: PositionType = PositionType.RAW,
    ) -> None:
        """Set the goal position of a motor in the specified position type.

        Args:
            motor_id: The ID of the motor to set.
            position: The goal position to set.
            position_type: The position unit/representation of the input (default: RAW).
        """
        assert self.driver is not None, "Driver must be available to set goal position"
        raw_position = self._position_converter_cache.convert(
            motor_id, position_type, PositionType.RAW, position
        )
        self.driver.set_goal_position(motor_id=motor_id, position=raw_position)

    def bulk_get_goal_positions(
        self,
        motor_ids: list[MotorIDVar],
        position_type: PositionType = PositionType.RAW,
    ) -> dict[MotorIDVar, float | None]:
        """Get the last set goal positions of multiple motors in the specified position type.

        Args:
            motor_ids: List of motor IDs.
            position_type: The position unit/representation to return (default: RAW).
        Returns:
            Dict mapping motor_id -> last set goal position in the requested position type, or None if not set.
        """
        assert self.driver is not None, "Driver must be available to bulk get goal positions"
        raw_goal_positions = self.driver.bulk_get_goal_positions(motor_ids=motor_ids)
        converted_goal_positions: dict[MotorIDVar, float | None] = {}
        for motor_id, position in raw_goal_positions.items():
            converted_position = self._position_converter_cache.convert(
                motor_id, PositionType.RAW, position_type, position
            )
            converted_goal_positions[motor_id] = converted_position

        return converted_goal_positions

    def bulk_set_goal_positions(
        self,
        motor_positions: dict[MotorIDVar, float],
        position_type: PositionType = PositionType.RAW,
    ) -> None:
        """Set the goal positions of multiple motors in the specified position type.

        Args:
            motor_positions: Dict mapping motor_id -> goal position to set.
            position_type: The position unit/representation of the input (default: RAW).
        """
        assert self.driver is not None, "Driver must be available to bulk set goal positions"
        raw_motor_positions: dict[MotorIDVar, float] = {}
        for motor_id, position in motor_positions.items():
            raw_position = self._position_converter_cache.convert(
                motor_id, position_type, PositionType.RAW, position
            )
            raw_motor_positions[motor_id] = raw_position
        self.driver.bulk_set_goal_positions(motor_positions=raw_motor_positions)

    @staticmethod
    def serial_types() -> list[type]:
        """Return MotorBus subclasses that use serial interfaces.

        These class objects correspond to the implementations accepted by
        :meth:`create` for serial-based bus implementations.
        """
        # Import lazily to avoid import cycles
        from .dynamixel_motor_bus import DynamixelMotorBus
        from .feetech_motor_bus import FeetechMotorBus

        return [FeetechMotorBus, DynamixelMotorBus]

    @staticmethod
    def can_types() -> list[type]:
        """Return MotorBus subclasses that use CAN interfaces."""
        from .damiao_motor_bus import DamiaoMotorBus

        return [DamiaoMotorBus]

    # Abstract class-level API -------------------------------------------------
    @classmethod
    @abstractmethod
    def supported_baudrates(cls) -> list[int]:
        """Return list of supported baud/bit rates for this MotorBus implementation.

        The list must be ordered by preferred priority (highest-likelihood first).
        Subclasses MUST implement this method.
        """
        raise NotImplementedError

    @staticmethod
    def resolve_bus_class(motorbus_type: str | type["MotorBus[MotorIDVar]"]) -> type["MotorBus[MotorIDVar]"]:
        """Resolve a motorbus type identifier (string or class) to a MotorBus class.

        Public helper; centralizes mapping logic and avoids duplication.
        """
        # If it's already a class, return it
        if isinstance(motorbus_type, type):
            return motorbus_type

        key = str(motorbus_type).strip().lower().replace("_", "").replace("-", "")

        if key in ("feetech", "feetechmotorbus"):
            from .feetech_motor_bus import FeetechMotorBus

            return FeetechMotorBus
        elif key in ("dynamixel", "dynamixelmotorbus"):
            from .dynamixel_motor_bus import DynamixelMotorBus

            return DynamixelMotorBus
        elif key in ("damiao", "damiaomotorbus", "can", "canmotorbus"):
            from .damiao_motor_bus import DamiaoMotorBus

            return DamiaoMotorBus
        else:
            raise ValueError(f"Unknown MotorBus type: {motorbus_type}")

    @staticmethod
    def supported_baudrates_for(motorbus_type: str | type["MotorBus[MotorIDVar]"]) -> list[int]:
        """Return supported baudrates for a given motorbus type (string or class)."""
        cls = MotorBus.resolve_bus_class(motorbus_type)
        return cls.supported_baudrates()

    # Context manager support
    def __enter__(self) -> "MotorBus[MotorIDVar]":
        """Return self. :meth:`connect` must be called explicitly before entering."""
        return self

    def __exit__(self, exc_type: type | None, exc_val: BaseException | None, exc_tb: object | None) -> None:
        self.disconnect()

    @staticmethod
    def create(motorbus_type: str | type["MotorBus[MotorIDVar]"]) -> "MotorBus[MotorIDVar]":
        """Factory method to create an offline MotorBus instance by type name.

        The returned instance is not yet connected. Call :meth:`connect` with the
        interface and baud rate when a physical connection is needed.

        Args:
            motorbus_type: Either a string identifier (e.g., "feetech", "dynamixel", "damiao")
                          or a MotorBus subclass reference.

        Returns:
            An instance of a MotorBus subclass.

        Raises:
            ValueError: If the motorbus_type is unknown.
        """
        cls = MotorBus.resolve_bus_class(motorbus_type) if not isinstance(motorbus_type, type) else motorbus_type
        return cls()
