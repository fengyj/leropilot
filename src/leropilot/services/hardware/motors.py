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

import logging
import json
import importlib.resources
from typing import List, Dict, Optional, Tuple

from leropilot.models.hardware import (
    MotorInfo,
    MotorTelemetry,
    MotorBrand,
    InterfaceType,
    ProbeConnectionResult,
    MotorScanResult,
    MotorProtectionParams,
    ProtectionViolation,
    ProtectionStatus,
)
from leropilot.services.hardware.drivers.base import BaseMotorDriver
from leropilot.services.hardware.drivers.feetech import FeetechDriver
from leropilot.services.hardware.drivers.dynamixel import DynamixelDriver
from leropilot.services.hardware.drivers.damiao import DamiaoCAN_Driver
from leropilot.services.hardware.robot_config import RobotConfigService

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

    def __init__(self):
        """Initialize motor service and load motor specs"""
        self.robot_config = RobotConfigService()
        # Cache stores raw spec data including model_ids
        self._specs_cache: Dict[str, Dict[str, Dict]] = {}
        self._load_motor_specs()
        logger.info("MotorService initialized")

    # ============================================================================
    # Motor Protection Parameter Management
    # ============================================================================

    def _load_motor_specs(self) -> None:
        """Load motor specifications from motor_specs.json resource file."""
        try:
            # Use importlib.resources for robust resource loading
            resource_files = importlib.resources.files("leropilot.resources")
            specs_file = resource_files.joinpath("motor_specs.json")
            
            with specs_file.open("r", encoding="utf-8") as f:
                specs_data = json.load(f)
            
            # Store raw data to preserve model_ids for lookup
            for brand, models in specs_data.items():
                self._specs_cache[brand] = {}
                for model_name, params in models.items():
                    self._specs_cache[brand][model_name] = params
            
            logger.info(f"Loaded motor specs for {len(self._specs_cache)} brands")
        except Exception as e:
            logger.error(f"Error loading motor specs: {e}")

    def get_motor_specs(self, brand: str, model: str) -> Optional[MotorProtectionParams]:
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

    def get_spec_by_model_id(self, brand: str, model_id: int) -> Optional[Tuple[str, MotorProtectionParams]]:
        """
        Look up motor specs by numeric model ID.
        
        Args:
            brand: Motor brand
            model_id: Numeric model ID from motor scan
        
        Returns:
            Tuple of (model_name, MotorProtectionParams) if found, None otherwise
        """
        brand_lower = brand.lower()
        if brand_lower not in self._specs_cache:
            return None
        
        for model_name, spec_data in self._specs_cache[brand_lower].items():
            params = MotorProtectionParams(**spec_data)
            if model_id in params.model_ids:
                return (model_name, params)
        
        return None

    def get_protection_params(
        self,
        brand: str,
        model: str,
        user_overrides: Optional[Dict[str, float]] = None
    ) -> Optional[MotorProtectionParams]:
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

    def check_violations(
        self,
        params: MotorProtectionParams,
        telemetry: MotorTelemetry
    ) -> ProtectionStatus:
        """
        Check telemetry data for protection parameter violations.
        
        Args:
            params: Motor protection parameters
            telemetry: Current motor telemetry data
        
        Returns:
            ProtectionStatus with violations list
        """
        violations: List[ProtectionViolation] = []
        
        # Check temperature
        if telemetry.temperature >= params.temp_critical:
            violations.append(ProtectionViolation(
                type="temp_critical",
                value=telemetry.temperature,
                limit=params.temp_critical
            ))
        elif telemetry.temperature >= params.temp_warning:
            violations.append(ProtectionViolation(
                type="temp_warning",
                value=telemetry.temperature,
                limit=params.temp_warning
            ))
        
        # Check voltage
        if telemetry.voltage < params.voltage_min:
            violations.append(ProtectionViolation(
                type="voltage_low",
                value=telemetry.voltage,
                limit=params.voltage_min
            ))
        elif telemetry.voltage > params.voltage_max:
            violations.append(ProtectionViolation(
                type="voltage_high",
                value=telemetry.voltage,
                limit=params.voltage_max
            ))
        
        # Check current
        if telemetry.current > params.current_peak:
            violations.append(ProtectionViolation(
                type="current_peak_exceeded",
                value=telemetry.current,
                limit=params.current_peak
            ))
        elif telemetry.current > params.current_max:
            violations.append(ProtectionViolation(
                type="current_max_exceeded",
                value=telemetry.current,
                limit=params.current_max
            ))
        
        # Determine overall status
        if any(v.type in ["temp_critical", "voltage_low", "voltage_high", "current_peak_exceeded"] for v in violations):
            status = "critical"
        elif violations:
            status = "warning"
        else:
            status = "ok"
        
        return ProtectionStatus(status=status, violations=violations)

    def list_supported_motors(self, brand: Optional[str] = None) -> Dict[str, List[str]]:
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
        
        return {
            brand: list(models.keys())
            for brand, models in self._specs_cache.items()
        }

    # ============================================================================
    # Connection Probing and Motor Discovery
    # ============================================================================

    def probe_connection(
        self,
        interface: str,
        interface_type: str = "serial",
        probe_baud_list: Optional[List[int]] = None,
        probe_motor_ids: Optional[List[int]] = None,
    ) -> Optional[ProbeConnectionResult]:
        """
        Probe a communication interface to detect motor brand and parameters.

        Tries different baud rates and brands to auto-detect robot configuration.

        Args:
            interface: Communication interface ("COM11", "/dev/ttyUSB0", "can0", etc.)
            interface_type: "serial", "can", or "slcan"
            probe_baud_list: List of baud rates to try (serial only)
            probe_motor_ids: List of motor IDs to scan (default: 1-10 for quick check)

        Returns:
            ProbeConnectionResult with detected brand/baud, or None if no motors found
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

    def _probe_serial_port(
        self, port: str, baud_list: List[int], motor_ids: List[int]
    ) -> Optional[ProbeConnectionResult]:
        """Probe a serial port for motors"""
        for baud_rate in baud_list:
            # Try Dynamixel first (most common in robotic arms)
            motors = self._try_driver(DynamixelDriver, port, baud_rate, motor_ids)
            if motors:
                logger.info(f"Detected Dynamixel motors on {port} @ {baud_rate} baud")
                return ProbeConnectionResult(
                    interface=port,
                    interface_type=InterfaceType.SERIAL,
                    brand=MotorBrand.DYNAMIXEL,
                    baud_rate=baud_rate,
                    discovered_motors=motors,
                    suggested_robots=self.robot_config.suggest_robots(MotorBrand.DYNAMIXEL, motors)
                )

            # Try Feetech
            motors = self._try_driver(FeetechDriver, port, baud_rate, motor_ids)
            if motors:
                logger.info(f"Detected Feetech motors on {port} @ {baud_rate} baud")
                return ProbeConnectionResult(
                    interface=port,
                    interface_type=InterfaceType.SERIAL,
                    brand=MotorBrand.FEETECH,
                    baud_rate=baud_rate,
                    discovered_motors=motors,
                    suggested_robots=self.robot_config.suggest_robots(MotorBrand.FEETECH, motors)
                )

        logger.warning(f"No motors detected on port {port}")
        return None

    def _probe_can_interface(
        self, interface: str, interface_type: str, motor_ids: List[int]
    ) -> Optional[ProbeConnectionResult]:
        """Probe a CAN interface for Damiao motors"""
        for bitrate in STANDARD_CAN_BITRATES:
            motors = self._try_driver(DamiaoCAN_Driver, interface, bitrate, motor_ids)
            if motors:
                logger.info(f"Detected Damiao motors on {interface} @ {bitrate} bps")
                return ProbeConnectionResult(
                    interface=interface,
                    interface_type=InterfaceType(interface_type),
                    brand=MotorBrand.DAMIAO,
                    baud_rate=bitrate,
                    discovered_motors=motors,
                    suggested_robots=self.robot_config.suggest_robots(MotorBrand.DAMIAO, motors)
                )

        logger.warning(f"No motors detected on CAN interface {interface}")
        return None

    @staticmethod
    def _try_driver(
        driver_class, interface: str, rate: int, motor_ids: List[int]
    ) -> Optional[List[MotorInfo]]:
        """
        Try to connect with a driver and detect motors.

        Returns:
            List of MotorInfo if successful, None otherwise
        """
        try:
            driver = driver_class(interface, rate)
            if not driver.connect():
                return None

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
    ) -> Optional[BaseMotorDriver]:
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
        scan_range: Optional[List[int]] = None,
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
            MotorScanResult with list of discovered motors
        """
        logger.info(f"Scanning {brand} motors on {interface}...")

        driver = self.create_driver(interface, brand, interface_type, baud_rate)
        if not driver:
            logger.error(f"Failed to create driver for {brand}")
            return MotorScanResult(motors=[], scan_duration_ms=0)

        try:
            import time
            start_time = time.time()
            discovered = driver.scan_motors(scan_range)
            scan_duration_ms = (time.time() - start_time) * 1000
            
            # Get suggested robots based on discovered motors
            suggested = self.robot_config.suggest_robots(MotorBrand(brand.lower()), discovered)
            
            logger.info(f"Scan complete: found {len(discovered)} motors in {scan_duration_ms:.0f}ms")
            return MotorScanResult(
                motors=discovered, 
                scan_duration_ms=scan_duration_ms,
                suggested_robots=suggested if suggested else None
            )
        finally:
            driver.disconnect()

    # ============================================================================
    # Telemetry Operations
    # ============================================================================

    def read_telemetry(
        self,
        driver: BaseMotorDriver,
        motor_id: int,
    ) -> Optional[MotorTelemetry]:
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
        user_overrides: Optional[Dict[str, float]] = None,
    ) -> Optional[MotorTelemetry]:
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
        motor_ids: List[int],
    ) -> Dict[int, MotorTelemetry]:
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
        speed: Optional[int] = None,
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
        positions: Dict[int, int],
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
        motor_ids: List[int],
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
        motor_infos: List[MotorInfo],
    ) -> Tuple[bool, List[str]]:
        """
        Validate a list of discovered motors for consistency.

        Checks:
        - No duplicate motor IDs
        - All motors same brand
        - Motor IDs are within expected range for brand

        Args:
            motor_infos: List of MotorInfo objects

        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []

        if not motor_infos:
            return False, ["No motors provided"]

        # Check for duplicates
        ids = [m.id for m in motor_infos]
        if len(ids) != len(set(ids)):
            errors.append("Duplicate motor IDs detected")

        # Check ID ranges
        if any(id > 252 for id in ids):
            errors.append("Motor ID > 252 (max for serial bus)")

        return len(errors) == 0, errors
