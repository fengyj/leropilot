"""
Hardware manager singleton.

Manages complete device lifecycle:
- Persistence: ~/.leropilot/hardwares/list.json stores all known devices
- Device lifecycle: add, remove, list, get, update
- Device state tracking: available, offline, occupied
- Settings management: per-device configuration
- Device data directory management

Singleton pattern ensures single instance across application.
"""

import json
import logging
import shutil
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from leropilot.models.hardware import (
    Device,
    DeviceCategory,
    DeviceConfig,
    DeviceStatus,
    MotorCalibration,
    MotorConfig,
    MotorProtectionOverride,
)

logger = logging.getLogger(__name__)

# Device list persistence location
HARDWARE_DATA_DIR = Path.home() / ".leropilot" / "hardwares"
DEVICE_LIST_PATH = HARDWARE_DATA_DIR / "list.json"


class HardwareManager:
    """Singleton managing all known hardware devices"""

    _instance: Optional["HardwareManager"] = None
    _lock = threading.Lock()

    def __new__(cls) -> "HardwareManager":
        """Implement singleton pattern"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        """Initialize hardware manager (only once via singleton)"""
        if not hasattr(self, "_initialized"):
            self._devices: dict[str, Device] = {}
            # Driver caching removed for stateless API design
            self._initialized = True
            self._load_devices()
            logger.info("HardwareManager singleton initialized")

    @property
    def data_dir(self) -> Path:
        """Get hardware data directory."""
        return HARDWARE_DATA_DIR

    def _load_devices(self) -> None:
        """Load device list from disk"""
        try:
            if DEVICE_LIST_PATH.exists():
                with open(DEVICE_LIST_PATH, encoding="utf-8") as f:
                    data = json.load(f)

                for device_data in data.get("devices", []):
                    try:
                        device = Device(**device_data)
                        self._devices[device.id] = device
                    except Exception as e:
                        logger.warning(f"Error loading device {device_data.get('id')}: {e}")

                logger.info(f"Loaded {len(self._devices)} devices from {DEVICE_LIST_PATH}")
            else:
                logger.info("No device list found; starting with empty list")
        except Exception as e:
            logger.error(f"Error loading device list: {e}")

    def _load_device_config(self, device: Device) -> None:
        """Load detailed configuration from config.json into device object"""
        try:
            config_path = self.get_device_dir(device.id, device.category) / "config.json"
            if config_path.exists():
                with open(config_path, encoding="utf-8") as f:
                    data = json.load(f)
                    device.config = DeviceConfig(**data)
            else:
                # Initialize empty config if none exists
                device.config = DeviceConfig()
        except Exception as e:
            logger.warning(f"Error loading config for {device.id}: {e}")
            device.config = DeviceConfig()  # Fallback

    def _save_device_config(self, device: Device) -> None:
        """Save detailed configuration to config.json"""
        try:
            if not device.config:
                return

            config_path = self.get_device_dir(device.id, device.category) / "config.json"

            with open(config_path, "w", encoding="utf-8") as f:
                f.write(device.config.model_dump_json(indent=2))
        except Exception as e:
            logger.error(f"Error saving config for {device.id}: {e}")

    def _save_devices(self) -> None:
        """Save device list to disk"""
        try:
            HARDWARE_DATA_DIR.mkdir(parents=True, exist_ok=True)

            data = {
                "version": "1.0",
                "devices": [device.model_dump(mode="json") for device in self._devices.values()],
            }

            with open(DEVICE_LIST_PATH, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False, default=str)

            logger.debug(f"Saved {len(self._devices)} devices to {DEVICE_LIST_PATH}")
        except Exception as e:
            logger.error(f"Error saving device list: {e}")

    def ensure_unique_name(self, name: str, exclude_id: str | None = None) -> bool:
        """
        Check if a device name is unique.

        Args:
            name: Device name to check
            exclude_id: Optional device ID to exclude from check (for updates)

        Returns:
            True if name is unique, False otherwise
        """
        for device_id, device in self._devices.items():
            if device.name == name:
                if exclude_id is None or device_id != exclude_id:
                    return False
        return True

    def add_device(
        self,
        device_id: str,
        category: DeviceCategory,
        name: str,
        manufacturer: str | None = None,
        labels: dict[str, str] | None = None,
        connection_settings: dict[str, Any] | None = None,
    ) -> Device:
        """
        Add new device to manager.

        Args:
            device_id: Device serial number (must be unique, used as ID per spec)
            category: Device category (robot, controller, camera)
            name: User-friendly name (must be unique)
            manufacturer: Device manufacturer (from discovery)
            labels: Key-value labels for automation (e.g., {"leropilot.ai/role": "follower"})
            connection_settings: Device connection settings dict (baud_rate, brand, etc.)

        Returns:
            Created Device object

        Raises:
            ValueError: If device ID or name already exists
        """
        # Basic validation
        if not device_id or (isinstance(device_id, str) and device_id.strip() == ""):
            raise ValueError("device_id (serial number) is required")

        # Reject cameras being added - cameras are stateless and not managed
        if category == DeviceCategory.CAMERA:
            raise ValueError("Cameras are not managed devices; use snapshot/stream APIs instead")

        # Check for duplicate device ID
        if device_id in self._devices:
            raise ValueError(f"Device with ID '{device_id}' already exists")

        # Check for duplicate name
        if not self.ensure_unique_name(name):
            raise ValueError(f"Device name '{name}' is not unique")

        final_settings = connection_settings or {}

        # Create new device with empty config
        device = Device(
            id=device_id,
            category=category,
            name=name,
            status=DeviceStatus.AVAILABLE,
            manufacturer=manufacturer,
            labels=labels or {},
            connection_settings=final_settings,
            created_at=datetime.now(),
            config=DeviceConfig(),
        )

        # Handle Default Protection Logic for Robots
        # Note: Auto-population logic removed as 'model' field is deprecated.
        # Users should use 'motor-discover' (MotorService.probe_connection) to discover motors/SuggestedRobot
        # and then configure the device.
        if category == DeviceCategory.ROBOT:
            pass
        # Save specific config file
        self._save_device_config(device)

        self._devices[device_id] = device
        self._save_devices()  # Saves to list.json (lightweight)

        cat_val = category.value if hasattr(category, "value") else str(category)
        logger.info(f"Added device {device_id}: {name} ({cat_val})")
        return device

    def remove_device(self, device_id: str, delete_calibration: bool = False) -> bool:
        """
        Remove device from manager.

        Args:
            device_id: Device ID
            delete_calibration: Whether to delete calibration data and device files

        Returns:
            True if successful
        """
        if device_id not in self._devices:
            logger.warning(f"Device {device_id} not found")
            return False

        device = self._devices[device_id]

        # Delete device data files if requested
        if delete_calibration:
            self.delete_device_data(device_id, device.category)

        del self._devices[device_id]
        self._save_devices()

        logger.info(f"Removed device {device_id}")
        return True

    def get_device(self, device_id: str) -> Device | None:
        """
        Get device by ID.

        Args:
            device_id: Device ID (serial number)

        Returns:
            Device object or None if not found
        """
        device = self._devices.get(device_id)
        if device and not device.config:
            self._load_device_config(device)
        return device

    def list_devices(self, category: DeviceCategory | None = None, status: DeviceStatus | None = None) -> list[Device]:
        """
        List all devices (optionally filtered).

        Args:
            category: Filter by category (optional)
            status: Filter by status (optional)

        Returns:
            List of Device objects
        """
        devices = list(self._devices.values())

        if category:
            devices = [d for d in devices if d.category == category]

        if status:
            devices = [d for d in devices if d.status == status]

        return sorted(devices, key=lambda d: d.name)

    def update_device(
        self,
        device_id: str,
        name: str | None = None,
        labels: dict[str, str] | None = None,
        connection_settings: dict[str, Any] | None = None,
        config: dict[str, Any] | None = None,
    ) -> Device | None:
        """
        Update device metadata and configuration.

        Args:
            device_id: Device ID
            name: New name (optional, must be unique)
            labels: New labels dict (replaces existing)
            connection_settings: New connection settings dict (merged with existing)
            config: New config dict (merged with existing)

        Returns:
            Updated Device object or None if not found
        """
        if device_id not in self._devices:
            logger.warning(f"Device {device_id} not found")
            return None

        # Ensure config is loaded before update
        device = self.get_device(device_id)
        if device is None:
            logger.warning(f"Device {device_id} not found")
            return None

        # Check name uniqueness if changing
        if name is not None and name != device.name:
            if not self.ensure_unique_name(name, exclude_id=device_id):
                raise ValueError(f"Device name '{name}' is not unique")
            device.name = name

        # Labels are replaced, not merged
        if labels is not None:
            device.labels = labels

        if connection_settings is not None:
            device.connection_settings.update(connection_settings)

        if config is not None:
            if device.config is None:
                device.config = DeviceConfig()

            # Handle 'motors' update
            if "motors" in config:
                motors_update = config["motors"]
                if not device.config.motors:
                    device.config.motors = {}

                for joint_name, joint_data in motors_update.items():
                    # Get or create existing MotorConfig
                    if joint_name not in device.config.motors:
                        device.config.motors[joint_name] = MotorConfig()

                    target_motor_config = device.config.motors[joint_name]

                    # Update calibration
                    if "calibration" in joint_data:
                        if isinstance(joint_data["calibration"], dict):
                            target_motor_config.calibration = MotorCalibration(**joint_data["calibration"])
                        else:
                            target_motor_config.calibration = joint_data["calibration"]

                    # Update protection
                    if "protection" in joint_data:
                        if isinstance(joint_data["protection"], dict):
                            target_motor_config.protection = MotorProtectionOverride(**joint_data["protection"])
                        else:
                            target_motor_config.protection = joint_data["protection"]

            if "custom" in config:
                device.config.custom.update(config["custom"])

        self._save_devices()  # list.json

        # Save config if modified
        if config is not None:
            self._save_device_config(device)

        logger.info(f"Updated device {device_id}")
        return device

    def set_device_status(self, device_id: str, status: DeviceStatus) -> bool:
        """
        Update device status (available/offline/occupied).

        Note: Status is runtime state and not persisted to disk.

        Args:
            device_id: Device ID
            status: New status

        Returns:
            True if successful
        """
        device = self.get_device(device_id)
        if not device:
            return False

        device.status = status
        # Don't save to disk - status is runtime state
        logger.debug(f"Set device {device_id} status to {status.value}")
        return True

    def set_label(self, device_id: str, key: str, value: str) -> bool:
        """
        Set a label on device (key-value pair).

        Args:
            device_id: Device ID
            key: Label key (e.g., "leropilot.ai/role")
            value: Label value (e.g., "follower")

        Returns:
            True if successful
        """
        device = self.get_device(device_id)
        if not device:
            return False

        device.labels[key] = value
        self._save_devices()
        logger.info(f"Set label '{key}={value}' on device {device_id}")
        return True

    def remove_label(self, device_id: str, key: str) -> bool:
        """
        Remove a label from device.

        Args:
            device_id: Device ID
            key: Label key to remove

        Returns:
            True if label was removed, False if not found
        """
        device = self.get_device(device_id)
        if not device or key not in device.labels:
            return False

        del device.labels[key]
        self._save_devices()
        logger.info(f"Removed label '{key}' from device {device_id}")
        return True

    def get_devices_by_label(self, key: str, value: str | None = None) -> list[Device]:
        """
        Get all devices with specific label.

        Args:
            key: Label key to search for
            value: Optional label value to match (if None, matches any value)

        Returns:
            List of Device objects
        """
        result = []
        for device in self._devices.values():
            if key in device.labels:
                if value is None or device.labels[key] == value:
                    result.append(device)
        return result

    def get_device_dir(self, device_id: str, category: DeviceCategory) -> Path:
        """
        Get device-specific data directory.

        Creates the directory if it doesn't exist.

        Args:
            device_id: Device unique identifier
            category: Device category

        Returns:
            Path to device directory (e.g., ~/.leropilot/hardwares/robot/{device_id}/)
        """
        cat_str = category.value if hasattr(category, "value") else str(category)
        category_dir = HARDWARE_DATA_DIR / cat_str
        device_dir = category_dir / device_id
        device_dir.mkdir(parents=True, exist_ok=True)
        return device_dir

    def get_calibration_file(self, device_id: str, category: DeviceCategory) -> Path:
        """
        Get path to device calibration file.

        Args:
            device_id: Device unique identifier
            category: Device category

        Returns:
            Path to calibration.json
        """
        device_dir = self.get_device_dir(device_id, category)
        return device_dir / "calibration.json"

    def delete_device_data(self, device_id: str, category: DeviceCategory) -> None:
        """
        Delete all device-specific data files (calibration, URDF, etc.).

        Args:
            device_id: Device unique identifier
            category: Device category
        """
        device_dir = self.get_device_dir(device_id, category)

        if device_dir.exists():
            shutil.rmtree(device_dir)
            logger.info(f"Deleted device data directory: {device_dir}")

    def get_urdf_file(self, device_id: str, category: DeviceCategory) -> Path:
        """
        Get path to custom URDF file.

        Args:
            device_id: Device unique identifier
            category: Device category

        Returns:
            Path to custom.urdf
        """
        device_dir = self.get_device_dir(device_id, category)
        return device_dir / "custom.urdf"

        return device_dir / "custom.urdf"

    # Driver connection methods removed for stateless design.
    # Telemetry and other hardware-interacting APIs must manage their own connections
    # using MotorService directly, ensuring ports are closed after use.

    def get_device_stats(self) -> dict[str, Any]:
        """
        Get statistics about managed devices.

        Returns:
            Dict with device counts and status breakdown
        """
        devices = list(self._devices.values())

        stats: dict[str, Any] = {
            "total_devices": len(devices),
            "by_category": {},
            "by_status": {},
        }

        # Count by category
        for category in DeviceCategory:
            count = len([d for d in devices if d.category == category])
            if count > 0:
                stats["by_category"][category.value] = count

        # Count by status
        for status in DeviceStatus:
            count = len([d for d in devices if d.status == status])
            if count > 0:
                stats["by_status"][status.value] = count

        return stats

    def export_devices(self, export_path: str) -> bool:
        """
        Export device list for backup.

        Args:
            export_path: Path to export to

        Returns:
            True if successful
        """
        try:
            data = {
                "version": "1.0",
                "exported_at": datetime.now().isoformat(),
                "devices": [device.model_dump(mode="json") for device in self._devices.values()],
            }

            with open(export_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False, default=str)

            logger.info(f"Exported {len(self._devices)} devices to {export_path}")
            return True
        except Exception as e:
            logger.error(f"Error exporting devices: {e}")
            return False

    def import_devices(self, import_path: str, merge: bool = True) -> bool:
        """
        Import device list from file.

        Args:
            import_path: Path to import from
            merge: If True, merge with existing devices; if False, replace

        Returns:
            True if successful
        """
        try:
            with open(import_path, encoding="utf-8") as f:
                data = json.load(f)

            if not merge:
                self._devices.clear()

            for device_data in data.get("devices", []):
                try:
                    device = Device(**device_data)
                    self._devices[device.id] = device
                except Exception as e:
                    logger.warning(f"Error importing device: {e}")

            self._save_devices()

            logger.info(f"Imported devices from {import_path}")
            return True
        except Exception as e:
            logger.error(f"Error importing devices: {e}")
            return False


# Convenience function to get singleton instance
def get_hardware_manager() -> HardwareManager:
    """Get HardwareManager singleton instance"""
    return HardwareManager()
