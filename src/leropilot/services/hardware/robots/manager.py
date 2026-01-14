"""
Robot manager - core CRUD operations and persistence.

This module provides the RobotManager class for managing robot lifecycle,
persistence, and coordination with discovery/verification services.
"""

import copy
import json
import logging
import threading
import uuid
from typing import Any, Optional, cast

from leropilot.exceptions import (
    ResourceConflictError,
    ResourceNotFoundError,
)
from leropilot.models.hardware import (
    DeviceStatus,
    MotorLimit,
    MotorModelInfo,
    Robot,
    RobotDefinition,
)

from .discovery import MotorBusDiscovery, PendingDeviceBuilder
from .paths import get_robot_list_path
from .spec_service import RobotSpecService
from .status_manager import RobotStatusManager
from .verification import RobotVerificationService

logger = logging.getLogger(__name__)


class RobotManager:
    """Manage persisted robots list.json.

    Responsible for loading, caching, saving and removing robot entries from
    the centralized list file stored under AppConfig.paths.data_dir/hardwares/robots/list.json.
    """

    _instance: Optional["RobotManager"] = None
    _lock = threading.Lock()

    def __new__(cls) -> "RobotManager":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if not hasattr(self, "_initialized"):
            self._robots: dict[str, Robot] = {}
            self._lock = threading.RLock()

            # Initialize service dependencies
            self._spec_service = RobotSpecService()
            self._discovery_service = MotorBusDiscovery()
            self._verification_service = RobotVerificationService()
            self._status_manager = RobotStatusManager(self._discovery_service, self._verification_service)
            self._pending_builder = PendingDeviceBuilder()

            self._initialized = True
            self._load_robots()
            logger.info("RobotManager initialized")

    def _load_robots(self) -> None:
        """Load robots from persistent storage."""
        try:
            list_path = get_robot_list_path()
            if list_path.exists():
                with open(list_path, encoding="utf-8") as f:
                    data = json.load(f)
                for r in data.get("robots", []):
                    try:
                        # Normalize persisted data before constructing Robot objects
                        r_normalized = self._normalize_robot_data(r)
                        robot = Robot(**r_normalized)
                        self._normalize_robot(robot)
                        self._apply_protection_defaults(robot, prune=False)

                        # Loaded robots are offline by default until seen
                        robot.status = DeviceStatus.OFFLINE
                        self._robots[robot.id] = robot
                    except Exception as e:
                        logger.warning(f"Error loading robot {r.get('id')}: {e}")
                logger.info(f"Loaded {len(self._robots)} robots from {list_path}")
            else:
                logger.info("No robot list found; starting with empty list")
        except Exception as e:
            logger.error(f"Error loading robot list: {e}")

    def _normalize_robot_data(self, robot_data: dict) -> dict:
        """Normalize robot data loaded from disk.

        Handles:
        - Ensuring runtime-only fields like `interface` are present
        - Normalizing custom protection keys from legacy formats
        """
        r_copy = copy.deepcopy(robot_data)

        # Motor bus connections: ensure `interface` key exists (set to None if missing)
        mbc = r_copy.get("motor_bus_connections")
        if isinstance(mbc, dict):
            for _k, v in mbc.items():
                if isinstance(v, dict) and "interface" not in v:
                    v["interface"] = None

        # Custom protection settings: normalize keys to canonical tuple form
        cps = r_copy.get("custom_protection_settings")
        if isinstance(cps, dict):
            new_cps: dict = {}
            for k, val in cps.items():
                if isinstance(k, str):
                    # Split on either ',' or ':' and build a tuple
                    sep = "," if ("," in k and ":" not in k) else ":"
                    parts = [p.strip() for p in k.split(sep) if p.strip()]
                    if len(parts) >= 2:
                        brand = parts[0]
                        model = parts[1]
                        variant = parts[2] if len(parts) >= 3 else None
                        key_tuple = (brand, model, variant)
                    else:
                        key_tuple = (k,)
                    new_cps[key_tuple] = val
                elif isinstance(k, (list, tuple)):
                    if len(k) >= 2:
                        brand = str(k[0])
                        model = str(k[1])
                        variant = str(k[2]) if len(k) >= 3 else None
                        key_tuple = (brand, model, variant)
                    else:
                        key_tuple = tuple(k)
                    new_cps[key_tuple] = val
                else:
                    new_cps[k] = val
            r_copy["custom_protection_settings"] = new_cps

        return r_copy

    def list_robots(self, refresh_status: bool = False) -> list[Robot]:
        """Return all robots currently managed."""
        with self._lock:
            if refresh_status:
                self.refresh_status()
            return sorted(self._robots.values(), key=lambda r: r.name)

    def get_robot(self, robot_id: str, refresh_status: bool = False) -> Robot | None:
        """Get a specific robot by ID."""
        with self._lock:
            if refresh_status:
                self.refresh_status(robot_id=robot_id)
            return self._robots.get(robot_id)

    def get_robot_motor_models_info(self, robot_id: str) -> list[MotorModelInfo]:
        """Return a deduplicated list of MotorModelInfo entries for the robot's
        definition-based motor list.

        Args:
            robot_id: persisted robot id

        Returns:
            List of `MotorModelInfo` instances matching the robot definition.

        Raises:
            ResourceNotFoundError: if the robot ID does not exist.
        """
        with self._lock:
            robot = self._robots.get(robot_id)
            if robot is None:
                raise ResourceNotFoundError("hardware.robot_device.not_found", id=robot_id)

            defn = robot.definition
            if isinstance(defn, str):
                raise ValueError("Robot.definition must be a RobotDefinition, not a string")

            return self._get_robot_motor_models_info_internal(robot)

    def _get_robot_motor_models_info_internal(self, robot: Robot) -> list[MotorModelInfo]:
        """Internal helper to get motor models info for a Robot instance."""
        try:
            from leropilot.services.hardware.motor_drivers.base import MotorUtil
        except Exception:
            MotorUtil = None  # type: ignore

        defn = robot.definition
        if not defn or isinstance(defn, str) or not getattr(defn, "motor_buses", None):
            return []

        seen: set[tuple[str, str, str | None]] = set()
        results: list[MotorModelInfo] = []

        for mb_def in defn.motor_buses.values() if isinstance(defn.motor_buses, dict) else defn.motor_buses:
            for rmd in mb_def.motors.values() if isinstance(mb_def.motors, dict) else mb_def.motors:
                brand = getattr(rmd, "brand", None)
                model = getattr(rmd, "model", None)
                variant = getattr(rmd, "variant", None)
                if not model:
                    continue
                mi = None
                if MotorUtil is not None:
                    mi = MotorUtil.find_motor(brand or "", model, variant)
                if mi is None:
                    continue
                brand_val = mi.brand.value if mi.brand is not None else ""
                key = (
                    str(brand_val).lower(),
                    (mi.model or "").lower(),
                    (mi.variant or None),
                )
                if key in seen:
                    continue
                seen.add(key)
                results.append(mi)

        return results

    def _apply_protection_defaults(self, robot: Robot, prune: bool = False) -> None:
        """Merge or prune default protection settings.

        Args:
           prune: If True, remove settings that match defaults.
                  If False (default), add default settings where missing.
        """
        models_info = self._get_robot_motor_models_info_internal(robot)

        # Build defaults map: (brand, model, variant) -> {type: value}
        defaults_map: dict[tuple[str, str, str | None], dict[str, float]] = {}
        for mi in models_info:
            brand_val = str(mi.brand.value).lower() if mi.brand else ""
            model_val = str(mi.model).lower() if mi.model else ""
            key = (brand_val, model_val, mi.variant)
            defaults_map[key] = {k: v.value for k, v in mi.limits.items()}

        current_settings = robot.custom_protection_settings

        if prune:
            # Remove defaults
            keys_to_remove = []
            for key, limits in current_settings.items():
                lookup_key = (str(key[0]).lower(), str(key[1]).lower(), key[2])

                if lookup_key not in defaults_map:
                    continue

                default_limits = defaults_map[lookup_key]
                new_limits = []
                for limit in limits:
                    if limit.type in default_limits and default_limits[limit.type] == limit.value:
                        continue  # Prune
                    new_limits.append(limit)

                if not new_limits:
                    keys_to_remove.append(key)
                else:
                    current_settings[key] = new_limits

            for k in keys_to_remove:
                del current_settings[k]

        else:
            # Expand defaults (Add missing)
            for key, default_limits in defaults_map.items():
                if key not in current_settings:
                    current_settings[key] = []

                existing_limits = {limit.type: limit.value for limit in current_settings[key]}


                for type_name, val in default_limits.items():
                    if type_name not in existing_limits:
                        current_settings[key].append(MotorLimit(type=type_name, value=val))

    def _normalize_robot(self, robot: Robot) -> None:
        """Resolve definition ID strings into full RobotDefinition objects."""
        if isinstance(robot.definition, str):
            defn = self._spec_service.get_robot_definition(robot.definition)
            if defn is None:
                raise ResourceNotFoundError("hardware.robot_device.unknown_definition", id=robot.definition)
            robot.definition = defn

    def add_robot(self, robot: Robot) -> Robot:
        """Add a new robot to the manager."""
        with self._lock:
            if not robot.id or robot.id.strip() == "":
                robot.id = uuid.uuid4().hex

            self._normalize_robot(robot)

            if robot.id in self._robots:
                raise ResourceConflictError("hardware.robot_device.conflict_id", id=robot.id)

            self.verify_robot(robot)
            self._apply_protection_defaults(robot, prune=True)
            self._robots[robot.id] = robot
            self._save_robots()
            self._apply_protection_defaults(robot, prune=False)
            logger.info(f"Added robot {robot.id}: {robot.name}")
            return robot

    def update_robot(self, robot_id: str, verify: bool = True, **kwargs: object) -> Robot | None:
        """Update an existing robot.

        Args:
            robot_id: Persisted robot id to update
            verify: When True, run `verify_robot` on the updated robot before persisting
            **kwargs: Attributes to set on the Robot instance.

        Returns:
            The updated `Robot` on success

        Raises:
            ResourceNotFoundError: if robot doesn't exist
            ResourceConflictError/ValidationError: on verification failure
        """
        with self._lock:
            if robot_id not in self._robots:
                raise ResourceNotFoundError("hardware.robot_device.not_found", id=robot_id)

            # Merge provided updates into a fresh validated Robot instance
            current = self._robots[robot_id]
            merged = current.model_dump()
            for k, v in kwargs.items():
                merged[k] = v

            # Normalize custom_protection_settings keys from legacy formats if present
            merged = self._normalize_robot_data(merged)

            # Construct a new Robot object (runs pydantic validation & normalization)
            robot = Robot(**merged)
            self._normalize_robot(robot)

            # If requested, verify hardware now
            if verify:
                self.verify_robot(robot)

            # Persist only when verification (if requested) passed
            self._apply_protection_defaults(robot, prune=True)
            self._robots[robot_id] = robot
            self._save_robots()
            self._apply_protection_defaults(robot, prune=False)
            logger.info(f"Updated robot {robot_id}")
            return robot

    def remove_robot(self, robot_id: str) -> bool:
        """Remove a robot from the manager."""
        with self._lock:
            if robot_id not in self._robots:
                raise ResourceNotFoundError("hardware.robot_device.not_found", id=robot_id)
            del self._robots[robot_id]
            self._save_robots()
            logger.info(f"Removed robot {robot_id}")
            return True

    def _save_robots(self) -> None:
        """Save robots to persistent storage."""
        with self._lock:
            try:
                list_path = get_robot_list_path()
                data: dict[str, object] = {"version": "1.0", "robots": []}
                robots_list = cast(list, data["robots"])

                # Exclude transient robots from save
                for robot in self._robots.values():
                    if robot.is_transient:
                        continue
                    robot_dict = self._serialize_robot_for_save(robot)
                    robots_list.append(robot_dict)

                with open(list_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                logger.debug(f"Saved {len(robots_list)} robots to {list_path}")
            except Exception as e:
                logger.error(f"Error saving robots: {e}")

    def _serialize_robot_for_save(self, robot: Robot) -> dict[str, Any]:
        """Serialize a robot for saving to disk."""
        robot_dict = robot.model_dump(mode="json", exclude_none=True)

        # Remove runtime-only fields from motor_bus_connections
        mbc = robot_dict.get("motor_bus_connections")
        if isinstance(mbc, dict):
            for conn in mbc.values():
                if isinstance(conn, dict) and "interface" in conn:
                    del conn["interface"]

        # Normalize definition: if definition is a RobotDefinition and matches a known spec, store its id
        def_val = robot.definition
        if isinstance(def_val, RobotDefinition):
            # If this definition matches a known spec, store its id for compactness
            try:
                if self._spec_service.get_robot_definition(def_val.id):
                    robot_dict["definition"] = def_val.id
                else:
                    # Custom definition: serialize as object
                    robot_dict["definition"] = def_val.model_dump(mode="json", exclude_none=True)
            except Exception:
                # Fallback: attempt to dump model
                try:
                    robot_dict["definition"] = def_val.model_dump(mode="json", exclude_none=True)
                except Exception:
                    pass
        else:
            robot_dict["definition"] = def_val

        return robot_dict

    def get_pending_devices(self, lang: str = "en") -> list[Robot]:
        """Return a list of `Robot` objects representing discovered devices."""
        discovered_buses = self._discovery_service.discover_motor_buses()
        return self._pending_builder.build_pending_robots(discovered_buses, lang)

    def verify_robot(self, robot: Robot) -> bool:
        """Verify a robot against actual hardware.

        Raises:
            ResourceConflictError: when verification fails
            ValidationError: when configuration is invalid

        Returns:
            True on successful verification
        """
        return self._verification_service.verify_robot(robot)

    def refresh_status(self, robot_id: str | None = None) -> list[Robot] | Robot | None:
        """Refresh online/status state for a robot or all robots.

        Args:
            robot_id: Optional robot id to refresh (otherwise refresh all)

        Returns:
            If robot_id is None, returns list[Robot] of current robots after refresh.
            If robot_id is provided, returns the Robot instance after refresh, or
            None if the robot was transient and removed during refresh.
        """
        with self._lock:
            # If there are no persisted robots, skip any discovery work and return immediately.
            # This prevents unnecessary hardware scans when the robots list is empty.
            if robot_id is None and not self._robots:
                return []

            removed_ids, _ = self._status_manager.refresh_robot_status(self._robots, robot_id)

            # Remove transient robots that are offline
            for rid in removed_ids:
                try:
                    del self._robots[rid]
                except Exception:
                    pass

            # Return per robot or all
            if robot_id is None:
                return list(self._robots.values())
            else:
                return self._robots.get(robot_id)


# Singleton accessor
_robot_manager: RobotManager | None = None
_manager_lock = threading.Lock()


def get_robot_manager() -> RobotManager:
    """Get the singleton RobotManager instance."""
    global _robot_manager
    with _manager_lock:
        if _robot_manager is None:
            _robot_manager = RobotManager()
        return _robot_manager
