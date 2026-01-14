"""
Motor bus scanning, telemetry, and protection service.

High-level service for:
- Loading motor protection parameters from motor_specs.json
- Probing ports to detect motor brand and baud rate
- Scanning motor buses to discover all connected motors
- Reading real-time telemetry from motors with protection status
- Setting motor positions and torque
- Bulk operations on multiple motors
- Detecting protection parameter violations

Orchestrates driver layer (Feetech, Dynamixel, Damiao) without exposing protocol details.
"""

import importlib.resources
import json
import logging

from leropilot.exceptions import (
    ValidationError,
)
from leropilot.models.hardware import (
    InterfaceType,
    MotorBrand,
    MotorDiscoverResult,
    MotorModelInfo,
    MotorProtectionParams,
    MotorScanResult,
    MotorTelemetry,
    ProtectionStatus,
    ProtectionViolation,
)

from .motor_drivers.base import BaseMotorDriver
from .motor_drivers.damiao.drivers import DamiaoCAN_Driver
from .motor_drivers.dynamixel.drivers import DynamixelDriver
from .motor_drivers.feetech.drivers import FeetechDriver
from .robots import RobotSpecService

logger = logging.getLogger(__name__)

# Standard baud rates for motor buses (in descending order of likelihood)
STANDARD_BAUD_RATES = [1000000, 115200, 57600, 9600]

# CAN standard bit rates
STANDARD_CAN_BITRATES = [1000000, 500000, 250000]


class MotorService:
    """
    High-level service for motor bus operations and protection monitoring.

    Handles:
    - Protocol negotiation and driver selection
    - Motor scanning and control
    - Protection parameter management
    - Violation detection
    """

    def __init__(self) -> None:
        """Initialize motor service and load motor specs"""
        self.robot_config = RobotSpecService()
        # Cache stores raw spec data including model_ids
        self._specs_cache: dict[str, dict[str, dict]] = {}
        self._load_motor_specs()
        logger.info("MotorService initialized")

    # ============================================================================
    # Motor Protection Parameter Management
    # ============================================================================

    def _load_motor_specs(self) -> None:
        """Load motor specifications from motor_specs.json resource file."""
        try:
            # Use importlib.resources for robust resource loading
            # NOTE: motor_specs.json is deprecated and will be retired in favor of
            # typed protocol tables (e.g., services/hardware/*_tables.py). Keep
            # loading for backward compatibility until migration is complete.
            resource_files = importlib.resources.files("leropilot.resources")
            specs_file = resource_files.joinpath("motor_specs.json")

            with specs_file.open("r", encoding="utf-8") as f:
                specs_data = json.load(f)

            # Store raw data to preserve model_ids for lookup
            for brand, models in specs_data.items():
                self._specs_cache[brand] = {}
                for model_name, params in models.items():
                    self._specs_cache[brand][model_name] = params

            logger.warning(
                "Loaded legacy motor_specs.json (DEPRECATED)."
                " Model/limit data should be migrated to typed protocol tables."
            )
        except Exception as e:
            logger.error(f"Error loading motor specs: {e}")

    def get_motor_specs(self, brand: str, model: str) -> MotorProtectionParams | None:
        """
        Get built-in protection parameters for a motor model.

        Args:
            brand: Motor brand (dynamixel, feetech, damiao)
            model: Motor model name (e.g., XL330-M077)

        Returns:
            MotorProtectionParams if found, None otherwise
        """
        brand_lower = brand.lower()
        if brand_lower not in self._specs_cache:
            return None

        spec_data = self._specs_cache[brand_lower].get(model)
        if spec_data:
            return MotorProtectionParams(**spec_data)
        return None

    def get_model_info_by_model_id(self, brand: str, model_id: int) -> MotorModelInfo | None:
        """Return a `MotorModelInfo` from protocol tables for the given brand+model_id.

        This method **does not** consult `motor_specs.json` and is intended to be the
        primary lookup for new code. Returns `None` if no table contains the model.
        """
        brand_lower = brand.lower()

        # Brand-specific table lookups (prefer drivers' tables)
        if brand_lower == "feetech":
            from .motor_drivers.feetech.tables import models_for_id

            candidates = models_for_id(model_id)
            if not candidates:
                return None
            # prefer base model (variant==None)
            for c in candidates:
                if c.variant is None:
                    return c
            # otherwise return a base-like copy of the first candidate
            result = candidates[0].model_copy()
            result.variant = None
            return result

        if brand_lower == "dynamixel":
            from .motor_drivers.dynamixel.tables import DYNAMIXEL_MODELS_LIST

            candidates = [m for m in DYNAMIXEL_MODELS_LIST if int(model_id) in (m.model_ids or [])]
            if not candidates:
                return None
            # prefer base model (variant == None)
            for c in candidates:
                if c.variant is None:
                    return c
            return candidates[0]

        if brand_lower == "damiao":
            from .motor_drivers.damiao.tables import DAMAIO_MODELS_LIST

            candidates = [m for m in DAMAIO_MODELS_LIST if int(model_id) in (m.model_ids or [])]
            if not candidates:
                return None
            # prefer base model
            for c in candidates:
                if c.variant is None:
                    return c
            return candidates[0]

        # TODO: Add other protocol table lookups (dynamixel, damiao) when available
        return None

    def get_spec_by_model_id(self, brand: str, model_id: int) -> tuple[str, MotorProtectionParams] | None:
        """
        Legacy compatibility wrapper: try protocol table lookups first and convert
        to `MotorProtectionParams` when possible; fall back to legacy `motor_specs.json`.
        This wrapper exists to ease migration and will be removed once callers move
        to `get_model_info_by_model_id` and the JSON file is retired.
        """
        # Try typed protocol tables first (no JSON dependency)
        model_info = self.get_model_info_by_model_id(brand, model_id)
        if model_info:
            # Convert MotorModelInfo.limits -> MotorProtectionParams shape when possible
            limits = model_info.limits or {}
            from leropilot.models.hardware import MotorLimitTypes

            def get_limit_value(key: str) -> float | None:
                entry = limits.get(key)
                return entry.value if entry is not None else None

            temp_max_v = get_limit_value(MotorLimitTypes.TEMPERATURE_MAX_C)
            current_max_v = get_limit_value(MotorLimitTypes.CURRENT_MAX_MA)

            params = MotorProtectionParams(
                model_ids=list(getattr(model_info, "model_ids", [])),
                temp_warning=None,
                temp_critical=None,
                temp_max=(int(temp_max_v) if temp_max_v is not None else None),
                voltage_min=get_limit_value(MotorLimitTypes.VOLTAGE_MIN),
                voltage_max=get_limit_value(MotorLimitTypes.VOLTAGE_MAX),
                current_max=(int(current_max_v) if current_max_v is not None else None),
                current_peak=None,
                datasheet_url=None,
            )
            return (model_info.model, params)

        # Fallback to legacy JSON data (deprecated)
        brand_lower = brand.lower()
        if brand_lower not in self._specs_cache:
            return None

        matches: list[tuple[str, MotorProtectionParams]] = []
        for model_name, spec_data in self._specs_cache[brand_lower].items():
            params = MotorProtectionParams(**spec_data)
            if model_id in params.model_ids:
                matches.append((model_name, params))

        if not matches:
            return None

        # Prefer base model (model name without variant suffix) if present
        base_matches = [m for m in matches if "-" not in m[0]]
        if base_matches:
            # deterministic choice: first base match
            return base_matches[0]

        # If multiple matches and no base match, this is ambiguous
        if len(matches) > 1:
            raise ValidationError(
                "hardware.motor_device.ambiguous_model",
                model_id=model_id,
                brand=brand,
                matches=[m[0] for m in matches],
            )

        # Single match
        return matches[0]

    def get_protection_params(
        self, brand: str, model: str, user_overrides: dict[str, float] | None = None
    ) -> MotorProtectionParams | None:
        """
        Get effective protection parameters with user overrides applied.

        Args:
            brand: Motor brand
            model: Motor model name
            user_overrides: Optional user-defined parameter overrides

        Returns:
            MotorProtectionParams with overrides applied, or None if model not found
        """
        builtin_specs = self.get_motor_specs(brand, model)
        if not builtin_specs:
            return None

        if not user_overrides:
            return builtin_specs

        # Apply overrides
        params_dict = builtin_specs.model_dump()
        params_dict.update(user_overrides)

        return MotorProtectionParams(**params_dict)

    def check_violations(self, params: MotorProtectionParams, telemetry: MotorTelemetry) -> ProtectionStatus:
        """
        Check telemetry data for protection parameter violations.

        Args:
            params: Motor protection parameters
            telemetry: Current motor telemetry data

        Returns:
            ProtectionStatus with violations list
        """
        violations: list[ProtectionViolation] = []

        # Check temperature (only if limits present)
        if params.temp_critical is not None and telemetry.temperature >= params.temp_critical:
            violations.append(
                ProtectionViolation(type="temp_critical", value=telemetry.temperature, limit=params.temp_critical)
            )
        elif params.temp_warning is not None and telemetry.temperature >= params.temp_warning:
            violations.append(
                ProtectionViolation(type="temp_warning", value=telemetry.temperature, limit=params.temp_warning)
            )

        # Check voltage
        if params.voltage_min is not None and telemetry.voltage < params.voltage_min:
            violations.append(
                ProtectionViolation(type="voltage_low", value=telemetry.voltage, limit=params.voltage_min)
            )
        elif params.voltage_max is not None and telemetry.voltage > params.voltage_max:
            violations.append(
                ProtectionViolation(type="voltage_high", value=telemetry.voltage, limit=params.voltage_max)
            )

        # Check current
        if params.current_peak is not None and telemetry.current > params.current_peak:
            violations.append(
                ProtectionViolation(type="current_peak_exceeded", value=telemetry.current, limit=params.current_peak)
            )
        elif params.current_max is not None and telemetry.current > params.current_max:
            violations.append(
                ProtectionViolation(type="current_max_exceeded", value=telemetry.current, limit=params.current_max)
            )

        # Determine overall status
        if any(v.type in ["temp_critical", "voltage_low", "voltage_high", "current_peak_exceeded"] for v in violations):
            status = "critical"
        elif violations:
            status = "warning"
        else:
            status = "ok"

        return ProtectionStatus(status=status, violations=violations)

    def list_supported_motors(self, brand: str | None = None) -> dict[str, list[str]]:
        """
        List all supported motor models.

        Args:
            brand: Optional brand filter

        Returns:
            Dictionary mapping brand to list of model names
        """
        if brand:
            brand_lower = brand.lower()
            if brand_lower in self._specs_cache:
                return {brand_lower: list(self._specs_cache[brand_lower].keys())}
            return {}

        return {brand: list(models.keys()) for brand, models in self._specs_cache.items()}

    # ============================================================================
    # Connection Probing and Motor Discovery
    # ============================================================================

    def probe_connection(
        self,
        interface: str,
        interface_type: str = "serial",
        probe_baud_list: list[int] | None = None,
        probe_motor_ids: list[int] | None = None,
    ) -> MotorDiscoverResult | None:
        """
        Probe a communication interface to detect motor brand and parameters.

        Tries different baud rates and brands to auto-detect robot configuration.

        Args:
            interface: Communication interface ("COM11", "/dev/ttyUSB0", "can0", etc.)
            interface_type: "serial", "can", or "slcan"
            probe_baud_list: List of baud rates to try (serial only)
            probe_motor_ids: List of motor IDs to scan (default: 1-10 for quick check)

        Returns:
            MotorDiscoverResult with detected brand/baud, or None if no motors found
        """
        if probe_motor_ids is None:
            # Scan 1-10 to cover most common 6-DOF and 7-DOF arms for identification
            probe_motor_ids = list(range(1, 11))

        if probe_baud_list is None:
            probe_baud_list = STANDARD_BAUD_RATES

        logger.info(f"Probing {interface} (type={interface_type}) for motors...")

        # Handle serial ports
        if interface_type == "serial":
            return self._probe_serial_port(interface, probe_baud_list, probe_motor_ids)

        # Handle CAN interfaces
        elif interface_type in ["can", "slcan"]:
            return self._probe_can_interface(interface, interface_type, probe_motor_ids)

        logger.error(f"Unknown interface type: {interface_type}")
        return None

    def _probe_serial_port(self, port: str, baud_list: list[int], motor_ids: list[int]) -> MotorDiscoverResult | None:
        """Probe a serial port for motors"""
        for baud_rate in baud_list:
            # Try Dynamixel first (most common in robotic arms)
            motors = self._try_driver(DynamixelDriver, port, baud_rate, motor_ids)
            if motors:
                logger.info(f"Detected Dynamixel motors on {port} @ {baud_rate} baud")
                return MotorDiscoverResult(
                    interface=port,
                    interface_type=InterfaceType.SERIAL,
                    brand=MotorBrand.DYNAMIXEL,
                    baud_rate=baud_rate,
                    discovered_motors=motors,
                    suggested_robots=[],
                )

            # Try Feetech
            motors = self._try_driver(FeetechDriver, port, baud_rate, motor_ids)
            if motors:
                logger.info(f"Detected Feetech motors on {port} @ {baud_rate} baud")
                return MotorDiscoverResult(
                    interface=port,
                    interface_type=InterfaceType.SERIAL,
                    brand=MotorBrand.FEETECH,
                    baud_rate=baud_rate,
                    discovered_motors=motors,
                    suggested_robots=[],
                )

        # No motors found on serial port
        logger.warning(f"No motors detected on port {port}")
        return None

    def _probe_can_interface(
        self, interface: str, interface_type: str, motor_ids: list[int]
    ) -> MotorDiscoverResult | None:
        """Probe a CAN interface for Damiao motors"""
        for bitrate in STANDARD_CAN_BITRATES:
            motors = self._try_driver(DamiaoCAN_Driver, interface, bitrate, motor_ids)
            if motors:
                logger.info(f"Detected Damiao motors on {interface} @ {bitrate} bps")
                return MotorDiscoverResult(
                    interface=interface,
                    interface_type=InterfaceType(interface_type),
                    brand=MotorBrand.DAMIAO,
                    baud_rate=bitrate,
                    discovered_motors=motors,
                    suggested_robots=[],
                )

        logger.warning(f"No motors detected on CAN interface {interface}")
        return None

    def _try_driver(
        self, driver_class: type[BaseMotorDriver], interface: str, rate: int, motor_ids: list[int]
    ) -> dict[int, MotorModelInfo] | None:
        """
        Try to connect with a driver and detect motors.

        Returns:
            Mapping of motor_id -> MotorModelInfo if successful, None otherwise
        """
        try:
            from leropilot.utils.unix import UdevManager

            driver = driver_class(interface, rate)

            def _try_connect() -> BaseMotorDriver | None:
                try:
                    return driver if driver.connect() else None
                except Exception:
                    return None

            udev_manager = UdevManager()
            connected_driver = udev_manager.ensure_device_access_with_retry(interface, _try_connect, subsystem="tty")

            if not connected_driver:
                return None
            driver = connected_driver

            # Use scan_motors with the limited range for speed and model info
            detected = driver.scan_motors(scan_range=motor_ids)
            driver.disconnect()

            if detected:
                return detected
            return None
        except Exception as e:
            logger.debug(f"Driver {driver_class.__name__} failed: {e}")
            return None

    # ============================================================================
    # Driver Management
    # ============================================================================

    def create_driver(
        self,
        interface: str,
        brand: str,
        interface_type: str = "serial",
        baud_rate: int = 1000000,
    ) -> BaseMotorDriver | None:
        """
        Create and connect a motor driver.

        Args:
            interface: Communication interface
            brand: Motor brand ("dynamixel", "feetech", "damiao")
            interface_type: "serial", "can", or "slcan"
            baud_rate: Baud/bit rate

        Returns:
            Connected driver instance or None if connection failed
        """
        try:
            driver: BaseMotorDriver
            if brand.lower() == "dynamixel":
                driver = DynamixelDriver(interface, baud_rate)
            elif brand.lower() == "feetech":
                driver = FeetechDriver(interface, baud_rate)
            elif brand.lower() == "damiao":
                driver = DamiaoCAN_Driver(interface, baud_rate)
            else:
                logger.error(f"Unknown motor brand: {brand}")
                return None

            if driver.connect():
                logger.info(f"Connected {brand} driver on {interface}")
                return driver
            else:
                logger.error(f"Failed to connect {brand} driver on {interface}")
                return None
        except Exception as e:
            logger.error(f"Error creating driver: {e}")
            return None

    def scan_motors(
        self,
        interface: str,
        brand: str,
        interface_type: str = "serial",
        baud_rate: int = 1000000,
        scan_range: list[int] | None = None,
    ) -> MotorScanResult:
        """
        Scan motor bus and discover all connected motors.

        Args:
            interface: Communication interface
            brand: Motor brand
            interface_type: "serial", "can", or "slcan"
            baud_rate: Baud/bit rate
            scan_range: List of motor IDs to scan (default: 1-253 for serial, 1-127 for CAN)

        Returns:
            MotorScanResult with mapping of discovered motors (id -> MotorModelInfo)
        """
        logger.info(f"Scanning {brand} motors on {interface}...")

        driver = self.create_driver(interface, brand, interface_type, baud_rate)
        if not driver:
            logger.error(f"Failed to create driver for {brand}")
            return MotorScanResult(motors={}, scan_duration_ms=0)  # empty dict matches expected type

        try:
            import time

            start_time = time.time()
            discovered = driver.scan_motors(scan_range)
            scan_duration_ms = (time.time() - start_time) * 1000

            # No compatibility suggestion behaviour; `suggested_robots` remains unset

            logger.info(f"Scan complete: found {len(discovered)} motors in {scan_duration_ms:.0f}ms")
            return MotorScanResult(motors=discovered, scan_duration_ms=scan_duration_ms, suggested_robots=None)
        finally:
            driver.disconnect()

    # ============================================================================
    # Telemetry Operations
    # ============================================================================

    def read_telemetry(
        self,
        driver: BaseMotorDriver,
        motor_id: int,
    ) -> MotorTelemetry | None:
        """
        Read telemetry from a single motor.

        Args:
            driver: Connected motor driver
            motor_id: Motor ID

        Returns:
            MotorTelemetry or None if read fails
        """
        try:
            return driver.read_telemetry(motor_id)
        except Exception as e:
            logger.error(f"Error reading telemetry from motor {motor_id}: {e}")
            return None

    def read_telemetry_with_protection(
        self,
        driver: BaseMotorDriver,
        motor_id: int,
        brand: str,
        model: str,
        user_overrides: dict[str, float] | None = None,
    ) -> MotorTelemetry | None:
        """
        Read telemetry from a motor and check protection status.

        Args:
            driver: Connected motor driver
            motor_id: Motor ID
            brand: Motor brand
            model: Motor model name
            user_overrides: Optional protection parameter overrides

        Returns:
            MotorTelemetry with protection_status populated, or None if read fails
        """
        telemetry = self.read_telemetry(driver, motor_id)
        if not telemetry:
            return None

        # Get protection parameters
        params = self.get_protection_params(brand, model, user_overrides)
        if params:
            telemetry.protection_status = self.check_violations(params, telemetry)

        return telemetry

    def read_bulk_telemetry(
        self,
        driver: BaseMotorDriver,
        motor_ids: list[int],
    ) -> dict[int, MotorTelemetry]:
        """
        Read telemetry from multiple motors efficiently.

        Args:
            driver: Connected motor driver
            motor_ids: List of motor IDs

        Returns:
            Dict mapping motor_id -> telemetry
        """
        try:
            return driver.read_bulk_telemetry(motor_ids)
        except Exception as e:
            logger.error(f"Error reading bulk telemetry: {e}")
            return {}

    # ============================================================================
    # Motor Control Operations
    # ============================================================================

    def set_position(
        self,
        driver: BaseMotorDriver,
        motor_id: int,
        position: int,
        speed: int | None = None,
    ) -> bool:
        """
        Set motor target position.

        Args:
            driver: Connected motor driver
            motor_id: Motor ID
            position: Target position (raw motor units)
            speed: Optional movement speed

        Returns:
            True if successful
        """
        try:
            return driver.set_position(motor_id, position, speed)
        except Exception as e:
            logger.error(f"Error setting position for motor {motor_id}: {e}")
            return False

    def bulk_set_position(
        self,
        driver: BaseMotorDriver,
        positions: dict[int, int],
    ) -> bool:
        """
        Set positions for multiple motors.

        Args:
            driver: Connected motor driver
            positions: Dict mapping motor_id -> position

        Returns:
            True if all successful
        """
        try:
            success = True
            for motor_id, position in positions.items():
                if not driver.set_position(motor_id, position):
                    success = False
            return success
        except Exception as e:
            logger.error(f"Error in bulk set position: {e}")
            return False

    def set_torque(
        self,
        driver: BaseMotorDriver,
        motor_id: int,
        enabled: bool,
    ) -> bool:
        """
        Enable or disable motor torque.

        Args:
            driver: Connected motor driver
            motor_id: Motor ID
            enabled: True to enable, False to disable

        Returns:
            True if successful
        """
        try:
            return driver.set_torque(motor_id, enabled)
        except Exception as e:
            logger.error(f"Error setting torque for motor {motor_id}: {e}")
            return False

    def bulk_set_torque(
        self,
        driver: BaseMotorDriver,
        motor_ids: list[int],
        enabled: bool,
    ) -> bool:
        """
        Set torque for multiple motors at once.

        Args:
            driver: Connected motor driver
            motor_ids: List of motor IDs
            enabled: True to enable, False to disable

        Returns:
            True if all successful
        """
        try:
            return driver.bulk_set_torque(motor_ids, enabled)
        except Exception as e:
            logger.error(f"Error in bulk set torque: {e}")
            return False

    def reboot_motor(
        self,
        driver: BaseMotorDriver,
        motor_id: int,
    ) -> bool:
        """
        Reboot a motor.

        Args:
            driver: Connected motor driver
            motor_id: Motor ID

        Returns:
            True if successful
        """
        try:
            return driver.reboot_motor(motor_id)
        except Exception as e:
            logger.error(f"Error rebooting motor {motor_id}: {e}")
            return False

    # ============================================================================
    # Validation
    # ============================================================================

    def validate_motor_configuration(
        self,
        motor_infos: dict[int, MotorModelInfo],
    ) -> tuple[bool, list[str]]:
        """
        Validate a mapping of discovered motors for consistency.

        Checks:
        - No duplicate motor IDs (keys)
        - Motor IDs are within expected range for serial buses

        Args:
            motor_infos: Mapping of motor_id -> MotorModelInfo

        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors: list[str] = []

        if not motor_infos:
            return False, ["No motors provided"]

        ids = list(motor_infos.keys())

        # Check for duplicates (mapping keys are unique by definition, but ensure they are ints)
        if any(not isinstance(i, int) for i in ids):
            errors.append("Motor IDs must be integers")

        # Check ID ranges
        if any(i > 252 for i in ids):
            errors.append("Motor ID > 252 (max for serial bus)")

        return len(errors) == 0, errors
