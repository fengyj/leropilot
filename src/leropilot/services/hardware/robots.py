"""
Robots-related hardware services.

This module consolidates robot discovery (previously `discovery.py`) and
robot configuration (previously `robot_config.py`). It exposes:

- `RobotsDiscoveryService` — discovery of serial ports -> robots
- `RobotConfigService` — loading/suggesting robot definitions

This module is the canonical location for robot-related services; the older
modules (`discovery.py`, `robot_config.py`) provide deprecation shims.
"""

import importlib.resources
import json
import logging
from pathlib import Path
from typing import Optional

from leropilot.models.hardware import (
    DeviceStatus,
    DiscoveredController,
    DiscoveredRobot,
    DiscoveryResult,
    MotorBrand,
    MotorCalibration,
    MotorInfo,
    RobotDefinition,
    SuggestedRobot,
)
from leropilot.services.hardware.platform_adapter import PlatformAdapter

logger = logging.getLogger(__name__)


class RobotsDiscoveryService:
    """Robot-focused hardware discovery service using platform adapter"""

    def __init__(self) -> None:
        """Initialize discovery service"""
        self.adapter = PlatformAdapter()
        logger.info(f"RobotsDiscoveryService initialized for {self.adapter.platform}")

    def discover_all(self) -> DiscoveryResult:
        """
        Perform full hardware discovery for robots/controllers.

        Returns:
            DiscoveryResult with all discovered devices
        """
        logger.info("Starting robot discovery...")

        serial_ports = self.adapter.discover_serial_ports()
        robots = self._serial_ports_to_robots(serial_ports)

        can_interfaces = self.adapter.discover_can_interfaces()
        controllers = self._can_interfaces_to_controllers(can_interfaces)

        result = DiscoveryResult(
            robots=robots,
            controllers=controllers,
        )

        logger.info(f"Discovery complete: {len(robots)} robots, {len(controllers)} controllers")
        return result

    def discover_serial_ports(self) -> list[DiscoveredRobot]:
        """
        Discover only serial ports (robots).

        Returns:
            List of DiscoveredRobot objects
        """
        serial_ports = self.adapter.discover_serial_ports()
        return self._serial_ports_to_robots(serial_ports)


    def discover_can_interfaces(self) -> list[DiscoveredController]:
        """
        Discover only CAN interfaces (controllers).

        Returns:
            List of DiscoveredController objects
        """
        can_interfaces = self.adapter.discover_can_interfaces()
        return self._can_interfaces_to_controllers(can_interfaces)

    @staticmethod
    def _serial_ports_to_robots(serial_ports: list[dict]) -> list[DiscoveredRobot]:
        """Convert serial port data to DiscoveredRobot objects"""
        robots = []
        for port in serial_ports:
            # Filter: only include ports that look like motor controllers
            # (ignore debug ports, etc.)
            description = port.get("description", "").lower()
            if any(keyword in description for keyword in ["ftdi", "ch340", "prolific", "serial"]):
                serial = port.get("serial_number")
                supported = True
                unsupported_reason = None
                if not serial:
                    supported = False
                    unsupported_reason = "missing_serial_number"

                robot = DiscoveredRobot(
                    port=port["port"],
                    description=port["description"],
                    serial_number=serial,
                    manufacturer=port.get("manufacturer", "Unknown"),
                    vid=port.get("vid"),
                    pid=port.get("pid"),
                    status=DeviceStatus.AVAILABLE,
                    supported=supported,
                    unsupported_reason=unsupported_reason,
                )
                robots.append(robot)

        return robots


    @staticmethod
    def _can_interfaces_to_controllers(can_interfaces: list[dict]) -> list[DiscoveredController]:
        """Convert CAN interface data to DiscoveredController objects"""
        controllers = []
        for interface in can_interfaces:
            controller = DiscoveredController(
                channel=interface["interface"],
                description=f"CAN Interface {interface['interface']}",
                vid="0000",
                pid="0000",
                manufacturer="Native",
                status=DeviceStatus.AVAILABLE,
            )
            controllers.append(controller)

        return controllers


# --------------------------- Robot Config Service ---------------------------

class RobotConfigService:
    """
    Service for loading and matching robot configurations.

    Loads robot definitions from robots.json and provides methods to match
    detected hardware against known robot models.
    """

    def __init__(self, config_path: Path | None = None) -> None:
        """
        Initialize robot config service.

        Args:
            config_path: Path to robots.json. If None, uses default resource path.
        """
        self.config_path = config_path
        self.robots = self._load_config()

    def _load_config(self) -> list[RobotDefinition]:
        """Load robot definitions from JSON."""
        try:
            if self.config_path is not None:
                # Load from explicit path
                if self.config_path.exists():
                    with open(self.config_path, encoding="utf-8") as f:
                        data = json.load(f)
                else:
                    logger.warning(f"Robots config not found at {self.config_path}")
                    return []
            else:
                # Load from package resources
                resource_files = importlib.resources.files("leropilot.resources")
                config_file = resource_files.joinpath("robots.json")
                with config_file.open("r", encoding="utf-8") as f:
                    data = json.load(f)

            robots_data = data.get("robots", [])
            robots = [RobotDefinition(**r) for r in robots_data]
            logger.info(f"Loaded {len(robots)} robot definitions")
            return robots
        except Exception as e:
            logger.error(f"Failed to load robots config: {e}")
            return []

    def get_robot_definition(self, robot_id: str) -> RobotDefinition | None:
        """
        Get robot definition by ID.

        Args:
            robot_id: Robot ID to look up

        Returns:
            RobotDefinition if found, None otherwise
        """
        for robot in self.robots:
            if robot.id == robot_id:
                return robot
        return None

    def suggest_robots(self, brand: MotorBrand, motors: list[MotorInfo]) -> list[SuggestedRobot]:
        """
        Suggest robot models based on detected motors.

        Args:
            brand: The motor brand detected on the bus
            motors: List of detected motors with ID and model info

        Returns:
            List of matching SuggestedRobot objects
        """
        detected_map = {m.id: m for m in motors}
        detected_ids = sorted(detected_map.keys())
        suggestions = []

        brand_str = brand.value.lower() if hasattr(brand, "value") else str(brand).lower()

        logger.debug(f"Suggesting robots for brand={brand_str}, ids={detected_ids}")

        for robot in self.robots:
            # Get motors from definition that match the current brand
            brand_motors = [m for m in robot.motors if m.brand.lower() == brand_str]

            if not brand_motors:
                continue

            # Check if the IDs match exactly for this brand's subset
            brand_ids = sorted([m.id for m in brand_motors])

            if brand_ids == detected_ids:
                # IDs match, now check models and variants for each motor
                match = True
                for req_motor in brand_motors:
                    mid = req_motor.id
                    det_motor = detected_map[mid]

                    # Check base model
                    if req_motor.model:
                        if req_motor.model.lower() not in det_motor.model.lower():
                            match = False
                            break

                    # Check variant (if specified in config)
                    if req_motor.variant and det_motor.variant:
                        # Only enforce variant match if the hardware actually reported one
                        if req_motor.variant.lower() not in det_motor.variant.lower():
                            match = False
                            break

                if match:
                    logger.info(f"Matched robot: {robot.display_name or robot.id}")
                    suggestions.append(
                        SuggestedRobot(
                            id=robot.id, lerobot_name=robot.lerobot_name or "", display_name=robot.display_name
                        )
                    )

        return suggestions


# --------------------------- Calibration Service ---------------------------

# Default calibration directory
CALIBRATION_BASE_DIR = Path.home() / ".leropilot" / "hardwares"

class CalibrationService:
    """Manages motor calibration data persistence and retrieval"""

    def __init__(self) -> None:
        """Initialize calibration service"""
        logger.info("CalibrationService initialized")
        CALIBRATION_BASE_DIR.mkdir(parents=True, exist_ok=True)

    def get_calibration_dir(self, device_id: str) -> Path:
        """Get calibration directory for a device."""
        calib_dir = CALIBRATION_BASE_DIR / device_id
        calib_dir.mkdir(parents=True, exist_ok=True)
        return calib_dir

    def get_calibration_file(self, device_id: str) -> Path:
        """Get calibration file path for a device."""
        return self.get_calibration_dir(device_id) / "calibration.json"

    def save_calibration(self, device_id: str, calibration_data: dict[int, "MotorCalibration"]) -> bool:
        """Save calibration data to disk."""
        try:
            calib_file = self.get_calibration_file(device_id)
            data_to_save: dict[str, dict] = {}
            for motor_id, calib in calibration_data.items():
                data_to_save[str(motor_id)] = calib.model_dump()

            with open(calib_file, "w", encoding="utf-8") as f:
                json.dump(data_to_save, f, indent=2)

            logger.info(f"Saved calibration for device {device_id} to {calib_file}")
            return True
        except Exception as e:
            logger.error(f"Error saving calibration: {e}")
            return False

    def load_calibration(self, device_id: str) -> dict[int, "MotorCalibration"] | None:
        """Load calibration data from disk."""
        try:
            calib_file = self.get_calibration_file(device_id)
            if not calib_file.exists():
                logger.debug(f"No calibration file found for device {device_id}")
                return None

            with open(calib_file, encoding="utf-8") as f:
                data = json.load(f)

            calibration_data: dict[int, MotorCalibration] = {}
            for motor_id_str, calib_dict in data.items():
                motor_id = int(motor_id_str)
                calibration_data[motor_id] = MotorCalibration(**calib_dict)

            logger.info(f"Loaded calibration for device {device_id}")
            return calibration_data
        except Exception as e:
            logger.error(f"Error loading calibration: {e}")
            return None

    def save_motor_calibration(self, device_id: str, motor_id: int, calibration: "MotorCalibration") -> bool:
        """Save calibration for a single motor."""
        try:
            all_calib = self.load_calibration(device_id) or {}
            all_calib[motor_id] = calibration
            return self.save_calibration(device_id, all_calib)
        except Exception as e:
            logger.error(f"Error saving motor calibration: {e}")
            return False

    def load_motor_calibration(self, device_id: str, motor_id: int) -> Optional["MotorCalibration"]:
        """Load calibration for a single motor."""
        try:
            all_calib = self.load_calibration(device_id)
            if not all_calib or motor_id not in all_calib:
                return None
            return all_calib[motor_id]
        except Exception as e:
            logger.error(f"Error loading motor calibration: {e}")
            return None

    def get_default_calibration(self, motor_id: int) -> "MotorCalibration":
        """Get default calibration values for a motor."""
        return MotorCalibration(
            id=motor_id,
            drive_mode=0,
            homing_offset=0,
            range_min=0,
            range_max=4095,
        )

    def validate_calibration(self, calibration: "MotorCalibration") -> tuple[bool, list[str]]:
        """Validate calibration data for consistency."""
        errors: list[str] = []
        if calibration.range_min >= calibration.range_max:
            errors.append("range_min >= range_max")
        if calibration.homing_offset < calibration.range_min or calibration.homing_offset > calibration.range_max:
            errors.append("homing_offset outside range_min/range_max")
        if calibration.drive_mode not in [0, 1]:
            errors.append("drive_mode must be 0 or 1")
        if calibration.id < 1 or calibration.id > 253:
            errors.append("motor id must be between 1 and 253")
        return len(errors) == 0, errors

    def create_calibration_from_dict(self, data: dict[str, object]) -> Optional["MotorCalibration"]:
        """Create MotorCalibration from dict (e.g., API request)."""
        try:
            calib = MotorCalibration(**data)
            is_valid, errors = self.validate_calibration(calib)
            if not is_valid:
                logger.warning(f"Invalid calibration data: {errors}")
            return calib
        except Exception as e:
            logger.error(f"Error creating calibration from dict: {e}")
            return None

    def list_calibration_files(self) -> list[str]:
        """List all devices with calibration data."""
        try:
            devices: list[str] = []
            for device_dir in CALIBRATION_BASE_DIR.iterdir():
                if device_dir.is_dir():
                    calib_file = device_dir / "calibration.json"
                    if calib_file.exists():
                        devices.append(device_dir.name)
            return sorted(devices)
        except Exception as e:
            logger.error(f"Error listing calibration files: {e}")
            return []

    def delete_calibration(self, device_id: str) -> bool:
        """Delete calibration data for a device."""
        try:
            calib_file = self.get_calibration_file(device_id)
            if calib_file.exists():
                calib_file.unlink()
                logger.info(f"Deleted calibration for device {device_id}")
            return True
        except Exception as e:
            logger.error(f"Error deleting calibration: {e}")
            return False

    def export_calibration(self, device_id: str, export_path: str) -> bool:
        """Export calibration data to file (backup)."""
        try:
            calib = self.load_calibration(device_id)
            if not calib:
                logger.warning(f"No calibration found for device {device_id}")
                return False
            data_to_export: dict[str, dict] = {}
            for motor_id, cal_obj in calib.items():
                data_to_export[str(motor_id)] = cal_obj.model_dump()
            with open(export_path, "w", encoding="utf-8") as f:
                json.dump(data_to_export, f, indent=2)
            logger.info(f"Exported calibration to {export_path}")
            return True
        except Exception as e:
            logger.error(f"Error exporting calibration: {e}")
            return False

    def import_calibration(self, device_id: str, import_path: str) -> bool:
        """Import calibration data from file."""
        try:
            with open(import_path, encoding="utf-8") as f:
                data = json.load(f)
            calibration_data: dict[int, MotorCalibration] = {}
            for motor_id_str, calib_dict in data.items():
                motor_id = int(motor_id_str)
                calibration_data[motor_id] = MotorCalibration(**calib_dict)
            return self.save_calibration(device_id, calibration_data)
        except Exception as e:
            logger.error(f"Error importing calibration: {e}")
            return False
