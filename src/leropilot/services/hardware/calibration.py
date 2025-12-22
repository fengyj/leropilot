"""
Motor calibration data management service.

Handles:
- Saving calibration data to ~/.leropilot/hardwares/{device_id}/calibration.json
- Loading calibration data from disk
- Validating calibration data
- Default calibration values

Calibration data includes:
- Motor offset angles
- Joint limits (min/max)
- Zero positions
- Friction/inertia estimates
"""

import json
import logging
from pathlib import Path
from typing import Dict, Optional, List, Any

from leropilot.models.hardware import MotorCalibration

logger = logging.getLogger(__name__)

# Default calibration directory
CALIBRATION_BASE_DIR = Path.home() / ".leropilot" / "hardwares"


class CalibrationService:
    """Manages motor calibration data persistence and retrieval"""

    def __init__(self):
        """Initialize calibration service"""
        logger.info("CalibrationService initialized")
        # Ensure base directory exists
        CALIBRATION_BASE_DIR.mkdir(parents=True, exist_ok=True)

    def get_calibration_dir(self, device_id: str) -> Path:
        """
        Get calibration directory for a device.

        Args:
            device_id: Unique device identifier

        Returns:
            Path to calibration directory
        """
        calib_dir = CALIBRATION_BASE_DIR / device_id
        calib_dir.mkdir(parents=True, exist_ok=True)
        return calib_dir

    def get_calibration_file(self, device_id: str) -> Path:
        """
        Get calibration file path for a device.

        Args:
            device_id: Unique device identifier

        Returns:
            Path to calibration.json file
        """
        return self.get_calibration_dir(device_id) / "calibration.json"

    def save_calibration(
        self,
        device_id: str,
        calibration_data: Dict[int, MotorCalibration],
    ) -> bool:
        """
        Save calibration data to disk.

        Args:
            device_id: Device identifier
            calibration_data: Dict mapping motor_id -> MotorCalibration

        Returns:
            True if successful
        """
        try:
            calib_file = self.get_calibration_file(device_id)

            # Convert Pydantic models to dicts for JSON serialization
            data_to_save = {}
            for motor_id, calib in calibration_data.items():
                data_to_save[str(motor_id)] = calib.model_dump()

            with open(calib_file, "w") as f:
                json.dump(data_to_save, f, indent=2)

            logger.info(f"Saved calibration for device {device_id} to {calib_file}")
            return True
        except Exception as e:
            logger.error(f"Error saving calibration: {e}")
            return False

    def load_calibration(
        self,
        device_id: str,
    ) -> Optional[Dict[int, MotorCalibration]]:
        """
        Load calibration data from disk.

        Args:
            device_id: Device identifier

        Returns:
            Dict mapping motor_id -> MotorCalibration, or None if file doesn't exist
        """
        try:
            calib_file = self.get_calibration_file(device_id)

            if not calib_file.exists():
                logger.debug(f"No calibration file found for device {device_id}")
                return None

            with open(calib_file, "r") as f:
                data = json.load(f)

            # Convert JSON back to Pydantic models
            calibration_data = {}
            for motor_id_str, calib_dict in data.items():
                motor_id = int(motor_id_str)
                calibration_data[motor_id] = MotorCalibration(**calib_dict)

            logger.info(f"Loaded calibration for device {device_id}")
            return calibration_data
        except Exception as e:
            logger.error(f"Error loading calibration: {e}")
            return None

    def save_motor_calibration(
        self,
        device_id: str,
        motor_id: int,
        calibration: MotorCalibration,
    ) -> bool:
        """
        Save calibration for a single motor.

        Args:
            device_id: Device identifier
            motor_id: Motor ID
            calibration: MotorCalibration object

        Returns:
            True if successful
        """
        try:
            # Load existing calibration
            all_calib = self.load_calibration(device_id) or {}

            # Update single motor
            all_calib[motor_id] = calibration

            # Save back
            return self.save_calibration(device_id, all_calib)
        except Exception as e:
            logger.error(f"Error saving motor calibration: {e}")
            return False

    def load_motor_calibration(
        self,
        device_id: str,
        motor_id: int,
    ) -> Optional[MotorCalibration]:
        """
        Load calibration for a single motor.

        Args:
            device_id: Device identifier
            motor_id: Motor ID

        Returns:
            MotorCalibration or None if not found
        """
        try:
            all_calib = self.load_calibration(device_id)
            if not all_calib or motor_id not in all_calib:
                return None

            return all_calib[motor_id]
        except Exception as e:
            logger.error(f"Error loading motor calibration: {e}")
            return None

    def get_default_calibration(self, motor_id: int) -> MotorCalibration:
        """
        Get default calibration values for a motor.

        Args:
            motor_id: Motor ID

        Returns:
            MotorCalibration with default values
        """
        return MotorCalibration(
            id=motor_id,
            drive_mode=0,  # Normal direction
            homing_offset=0,  # No offset
            range_min=0,  # Min raw encoder value
            range_max=4095,  # Max raw encoder value (12-bit)
        )

    def validate_calibration(self, calibration: MotorCalibration) -> tuple[bool, List[str]]:
        """
        Validate calibration data for consistency.

        Args:
            calibration: MotorCalibration object

        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []

        # Check range is valid
        if calibration.range_min >= calibration.range_max:
            errors.append("range_min >= range_max")

        # Check homing offset is within range
        if calibration.homing_offset < calibration.range_min or calibration.homing_offset > calibration.range_max:
            errors.append("homing_offset outside range_min/range_max")

        # Check drive_mode is valid
        if calibration.drive_mode not in [0, 1]:
            errors.append("drive_mode must be 0 or 1")

        # Check motor ID is valid
        if calibration.id < 1 or calibration.id > 253:
            errors.append("motor id must be between 1 and 253")

        return len(errors) == 0, errors

    def create_calibration_from_dict(self, data: Dict[str, Any]) -> Optional[MotorCalibration]:
        """
        Create MotorCalibration from dictionary (e.g., from API request).

        Args:
            data: Dictionary with calibration parameters

        Returns:
            MotorCalibration or None if invalid
        """
        try:
            calib = MotorCalibration(**data)
            is_valid, errors = self.validate_calibration(calib)
            if not is_valid:
                logger.warning(f"Invalid calibration data: {errors}")
            return calib
        except Exception as e:
            logger.error(f"Error creating calibration from dict: {e}")
            return None

    def list_calibration_files(self) -> List[str]:
        """
        List all devices with calibration data.

        Returns:
            List of device IDs that have calibration data
        """
        try:
            devices = []
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
        """
        Delete calibration data for a device.

        Args:
            device_id: Device identifier

        Returns:
            True if successful
        """
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
        """
        Export calibration data to file (for backup/sharing).

        Args:
            device_id: Device identifier
            export_path: Destination file path

        Returns:
            True if successful
        """
        try:
            calib = self.load_calibration(device_id)
            if not calib:
                logger.warning(f"No calibration found for device {device_id}")
                return False

            # Convert to dicts
            data_to_export = {}
            for motor_id, cal_obj in calib.items():
                data_to_export[str(motor_id)] = cal_obj.model_dump()

            with open(export_path, "w") as f:
                json.dump(data_to_export, f, indent=2)

            logger.info(f"Exported calibration to {export_path}")
            return True
        except Exception as e:
            logger.error(f"Error exporting calibration: {e}")
            return False

    def import_calibration(self, device_id: str, import_path: str) -> bool:
        """
        Import calibration data from file.

        Args:
            device_id: Device identifier
            import_path: Source file path

        Returns:
            True if successful
        """
        try:
            with open(import_path, "r") as f:
                data = json.load(f)

            # Convert to Pydantic models
            calibration_data = {}
            for motor_id_str, calib_dict in data.items():
                motor_id = int(motor_id_str)
                calibration_data[motor_id] = MotorCalibration(**calib_dict)

            # Save to device
            return self.save_calibration(device_id, calibration_data)
        except Exception as e:
            logger.error(f"Error importing calibration: {e}")
            return False
