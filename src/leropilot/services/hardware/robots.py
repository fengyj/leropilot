"""
Robots-related hardware services.

This module consolidates robot discovery (previously `discovery.py`) and
robot configuration (previously `robot_config.py`). It exposes:

- `RobotConfigService` — loading/suggesting robot definitions

This module is the canonical location for robot-related services; the older
modules (`discovery.py`, `robot_config.py`) provide deprecation shims.
"""

import importlib.resources
import json
import logging
import threading
from pathlib import Path
from importlib.abc import Traversable
from typing import TYPE_CHECKING, Any, Optional, cast, Iterator

if TYPE_CHECKING:
    from leropilot.services.hardware.motor_buses.motor_bus import MotorBus

from leropilot.models.hardware import (
    DeviceCategory,
    DeviceStatus,
    MotorBusDefinition,
    MotorModelInfo,
    Robot,
    RobotDefinition,
    RobotMotorBusConnection,
    RobotMotorDefinition,
    RobotVerificationError,
)
from leropilot.services.hardware.platform_adapter import PlatformAdapter

logger = logging.getLogger(__name__)


# --------------------------- Robot Config Service ---------------------------


class RobotSpecService:
    """
    Service for loading robot specifications.

    Loads robot definitions from `robot_specs.json` and provides methods to
    access the definitions. The loaded specs are cached in memory.
    """

    def __init__(self, config_path: Path | None = None) -> None:
        """
        Initialize robot spec service.

        Args:
            config_path: Optional path to `robot_specs.json`. If not provided, the
                         service will attempt to load from package resources via
                         `leropilot.utils.get_resources_dir()` or fallback to
                         `importlib.resources`.
        """
        self.config_path = config_path
        self._cached: list[RobotDefinition] | None = None

    def _load_config(self) -> list[RobotDefinition]:
        """Load robot specifications from JSON and cache the result."""
        try:
            data = None
            if self.config_path is not None:
                if self.config_path.exists():
                    with open(self.config_path, encoding="utf-8") as f:
                        data = json.load(f)
                else:
                    logger.warning(f"Robot specs not found at {self.config_path}")
            else:
                # Prefer configured resources dir when available
                try:
                    from leropilot.utils.paths import get_resources_dir

                    resources_dir = get_resources_dir()
                    spec_file = resources_dir / "robot_specs.json"
                    if spec_file.exists():
                        with open(spec_file, encoding="utf-8") as f:
                            data = json.load(f)
                    else:
                        # Fallback to package resource
                        resource_files = importlib.resources.files("leropilot.resources")
                        config_file = resource_files.joinpath("robot_specs.json")
                        with config_file.open("r", encoding="utf-8") as f:
                            data = json.load(f)
                except Exception:
                    # Final fallback: importlib.resources directly
                    resource_files = importlib.resources.files("leropilot.resources")
                    config_file = resource_files.joinpath("robot_specs.json")
                    with config_file.open("r", encoding="utf-8") as f:
                        data = json.load(f)

            robots_data = (data or {}).get("robots", [])
            robots = [RobotDefinition(**r) for r in robots_data]
            # Sort robots by display_name for consistent UI presentation
            robots.sort(key=lambda r: r.display_name)
            logger.info(f"Loaded {len(robots)} robot specifications")
            return robots
        except Exception as e:
            logger.error(f"Failed to load robot specifications: {e}")
            return []

    def get_all_definitions(self) -> list[RobotDefinition]:
        """Return all robot definitions, loading and caching them if necessary."""
        if self._cached is None:
            self._cached = self._load_config()
        return self._cached

    def get_robot_definition(self, robot_id: str) -> RobotDefinition | None:
        """
        Get robot definition by ID.

        Args:
            robot_id: Robot ID to look up

        Returns:
            RobotDefinition if found, None otherwise
        """
        for robot in self.get_all_definitions():
            if robot.id == robot_id:
                return robot
        return None


# --------------------------- Calibration Service ---------------------------

# Default hardare directory
HARDWARE_DATA_DIR = Path.home() / ".leropilot" / "hardwares"


class CalibrationService:
    """Manages motor calibration data persistence and retrieval"""

    def __init__(self) -> None:
        """Initialize calibration service"""
        logger.info("CalibrationService initialized")

    # NOTE: CalibrationService modifications will be performed later as requested.


# --------------------------- Robot Manager ---------------------------


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
            self._initialized = True
            self._load_robots()
            logger.info("RobotManager initialized")

    def _get_list_path(self) -> Path:
        from leropilot.services.config.manager import get_config

        cfg = get_config()
        data_dir = Path(cfg.paths.data_dir)
        list_path = data_dir / "hardwares" / "robots" / "list.json"
        list_path.parent.mkdir(parents=True, exist_ok=True)
        return list_path

    def _load_robots(self) -> None:
        try:
            list_path = self._get_list_path()
            if list_path.exists():
                with open(list_path, encoding="utf-8") as f:
                    data = json.load(f)
                for r in data.get("robots", []):
                    try:
                        robot = Robot(**r)
                        self._normalize_robot(robot)

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

    def list_robots(self, refresh_status: bool = False) -> list[Robot]:
        """Return all robots currently managed."""
        with self._lock:
            if refresh_status:
                self.refresh_status()
            return sorted(self._robots.values(), key=lambda r: r.name)

    def get_robot(self, robot_id: str, refresh_status: bool = False) -> Robot | None:
        with self._lock:
            if refresh_status:
                self.refresh_status(robot_id=robot_id)
            robot = self._robots.get(robot_id)
            return robot

    def get_robot_motor_models_info(self, robot_id: str) -> list[MotorModelInfo]:
        """Return a deduplicated list of MotorModelInfo entries for the robot's
        definition-based motor list.

        Args:
            robot_id: persisted robot id

        Returns:
            List of `MotorModelInfo` instances matching the robot definition.

        Raises:
            ValueError: if the robot ID does not exist.
        """
        # Use MotorUtil for table lookups
        try:
            from leropilot.services.hardware.motor_drivers.base import MotorUtil
        except Exception:
            MotorUtil = None  # type: ignore

        with self._lock:
            robot = self._robots.get(robot_id)
            if robot is None:
                raise ValueError("Robot not found")

            defn = robot.definition
            # Robot.definition must be a RobotDefinition object; string ids are not supported at runtime
            if isinstance(defn, str):
                raise ValueError("Robot.definition must be a RobotDefinition, not a string")
            if not defn or not getattr(defn, "motor_buses", None):
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
                        # not resolved via tables; skip
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


    def _normalize_robot(self, robot: Robot) -> None:
        """Resolve definition ID strings into full RobotDefinition objects."""
        if isinstance(robot.definition, str):
            spec = RobotSpecService()
            defn = spec.get_robot_definition(robot.definition)
            if defn is None:
                raise ValueError(f"Unknown robot definition id '{robot.definition}'")
            robot.definition = defn

    def add_robot(self, robot: Robot) -> Robot:
        with self._lock:
            if not robot.id or robot.id.strip() == "":
                import uuid

                robot.id = uuid.uuid4().hex
            
            self._normalize_robot(robot)

            if robot.id in self._robots:
                raise ValueError(f"Robot with ID '{robot.id}' already exists")

            self.verify_robot(robot)
            self._save_robots()
            self._robots[robot.id] = robot
            logger.info(f"Added robot {robot.id}: {robot.name}")
            return robot

    def update_robot(self, robot_id: str, verify: bool = True, **kwargs: object) -> Robot | None:
        """Update an existing robot.

        Args:
            robot_id: Persisted robot id to update
            verify: When True, run `verify_robot` on the updated robot before persisting; on
                    verification failure a `RobotVerificationError` will be raised and the
                    persisted state will not be changed.
            **kwargs: Attributes to set on the Robot instance.

        Returns:
            The updated `Robot` on success, or `None` when the robot does not exist.
        """
        with self._lock:
            if robot_id not in self._robots:
                logger.warning(f"Robot {robot_id} not found")
                return None
            robot = self._robots[robot_id].model_copy()
            for k, v in kwargs.items():
                # Apply provided values (including explicit None) — router is responsible
                # for distinguishing omitted parameters from explicit nulls.
                if hasattr(robot, k):
                    setattr(robot, k, v)

            self._normalize_robot(robot)

            # If requested, verify hardware now; verification errors propagate so callers
            # can decide how to map them (e.g., HTTP 409 in router layer).
            if verify:
                # verify_robot raises RobotVerificationError on failure
                self.verify_robot(robot)

            # Persist only when verification (if requested) passed
            self._save_robots()
            self._robots[robot_id] = robot
            logger.info(f"Updated robot {robot_id}")
            return robot

    def remove_robot(self, robot_id: str) -> bool:
        with self._lock:
            if robot_id not in self._robots:
                logger.warning(f"Robot {robot_id} not found")
                return False
            del self._robots[robot_id]
            self._save_robots()
            logger.info(f"Removed robot {robot_id}")
            return True

    def _save_robots(self) -> None:
        with self._lock:
            try:
                list_path = self._get_list_path()
                data: dict[str, object] = {"version": "1.0", "robots": []}
                # Exclude transient robots from save
                for robot in self._robots.values():
                    if robot.is_transient:
                        continue
                    robot_dict = robot.model_dump(mode="json", exclude_none=True)
                    # Normalize definition: if definition is a RobotDefinition and matches a known spec, store its id
                    from leropilot.services.hardware.robots import RobotSpecService

                    spec = RobotSpecService()
                    def_val = robot.definition
                    if isinstance(def_val, dict):
                        # already a dict representation
                        robot_dict["definition"] = def_val
                    elif isinstance(def_val, RobotDefinition):
                        # If this definition matches a known spec, store its id for compactness
                        try:
                            if spec.get_robot_definition(def_val.id):
                                robot_dict["definition"] = def_val.id
                            else:
                                robot_dict["definition"] = def_val
                        except Exception:
                            robot_dict["definition"] = def_val
                    elif isinstance(def_val, str):
                        # Already an id string; keep it (spec lookup optional)
                        robot_dict["definition"] = def_val
                    else:
                        robot_dict["definition"] = def_val

                        robots_list = cast(list, data["robots"])
                robots_list.append(robot_dict)

                with open(list_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                logger.debug("Saved %d robots to %s", len(robots_list), list_path)
                logger.debug(f"Saved {len(robots_list)} robots to {list_path}")
            except Exception as e:
                logger.error(f"Error saving robots: {e}")

    def _discover_motor_buses(
        self, filters: list[tuple[str, int | None]] | None = None
    ) -> list[tuple["MotorBus", "str | None", "str | None"]]:
        """Discover motor bus instances that have motors attached.

        The returned ``bus`` objects are lightweight proxies (disconnected) that
        expose `interface`, `baud_rate` and `motors` attributes. Implementations
        should not assume the underlying hardware connection remains open.

        Args:
            filters: Optional list of (motorbus_type, baudrate) pairs to restrict discovery.
                     If provided, only the specified motorbus types / baudrates will be tried.
        Returns:
            List[tuple]: list of tuples (bus_proxy, serial_number, manufacturer) for each
                         motorbus where motors were successfully found. `serial_number` and
                         `manufacturer` may be None when not available.
        """
        from leropilot.services.hardware.motor_buses.motor_bus import MotorBus

        adapter = PlatformAdapter()

        # Build allowed map from filters: class -> set(baudrates)
        allowed: dict[type, set[int] | None] = {}
        if filters:
            for t, baud in filters:
                try:
                    cls = MotorBus.resolve_bus_class(t)
                except Exception:
                    logger.debug(f"Unknown motorbus type in filters: {t}")
                    continue
                # Ensure an entry exists and is a set before adding
                if cls not in allowed:
                    allowed[cls] = set()
                if baud is not None:
                    vals = allowed.get(cls)
                    if vals is None:
                        allowed[cls] = set()
                        vals = allowed[cls]
                    # mypy can't always infer that vals is a set; assert its type
                    if isinstance(vals, set):
                        vals.add(int(baud))
                    else:
                        allowed[cls] = {int(baud)}
                else:
                    allowed[cls] = None

        results: list = []

        # Helper to check whether we should try a given class (and to get allowed baudrates)
        def _get_allowed_baudrates_for(cls: type) -> list[int] | None:
            # `cls` is assumed to be a MotorBus class with `supported_baudrates`.
            # Use a runtime Any cast to help mypy understand it has the attribute.
            if not filters:
                return (cast(Any, cls)).supported_baudrates()  # type: ignore[return-value]
            if cls not in allowed:
                return None
            vals = allowed[cls]
            if vals is None or len(vals) == 0:
                return (cast(Any, cls)).supported_baudrates()  # type: ignore[return-value]
            # preserve class ordering but filter to allowed set
            return [b for b in (cast(Any, cls)).supported_baudrates() if b in vals]

        # Discover serial ports and try serial-type motor buses unless filters exclude them
        serial_ports = adapter.discover_serial_ports()
        # If filters provided and none of the filtered classes are serial types, skip serial
        if filters:
            serial_classes = set(MotorBus.serial_types())
            if not any(cls in serial_classes for cls in allowed.keys()):
                serial_ports = []

        for port in serial_ports:
            port_name = port.port
            # collect metadata for returned tuple
            serial_number = port.serial_number
            manufacturer = port.manufacturer

            for cls in MotorBus.serial_types():
                baud_candidates = _get_allowed_baudrates_for(cls)
                if baud_candidates is None:
                    continue
                found = False
                for baud in baud_candidates:
                    bus = None
                    try:
                        bus = MotorBus.create(cls, port_name, baud)
                        if not bus.connect():
                            try:
                                bus.disconnect()
                            except Exception:
                                pass
                            continue

                        motors = bus.scan_motors()
                        if motors:
                            logger.info(f"Found motors on {port_name} using {cls.__name__} @ {baud}")
                            # Snapshot motors and disconnect to avoid leaving hardware open
                            motors_snapshot = dict(getattr(bus, "motors", {}))
                            try:
                                bus.disconnect()
                            except Exception:
                                pass

                            # Create lightweight proxy class so callers can inspect .motors, .interface, .baud_rate
                            BusProxy = type(cls.__name__, (), {})
                            bus_proxy = BusProxy()
                            bus_proxy.interface = port_name
                            bus_proxy.baud_rate = baud
                            bus_proxy.motors = motors_snapshot

                            results.append((bus_proxy, serial_number, manufacturer))
                            found = True
                            break
                        else:
                            try:
                                bus.disconnect()
                            except Exception:
                                pass
                    except Exception as e:
                        logger.debug(f"Error probing {cls} on {port_name} @ {baud}: {e}")
                        if bus is not None:
                            try:
                                bus.disconnect()
                            except Exception:
                                pass
                if found:
                    # Do not try other serial motorbus types for this port if one succeeded
                    break

        # Discover CAN interfaces and try CAN-type motor buses unless filters exclude them
        can_interfaces = adapter.discover_can_interfaces()
        if filters:
            can_classes = set(MotorBus.can_types())
            if not any(cls in can_classes for cls in allowed.keys()):
                can_interfaces = []

        for interface in can_interfaces:
            if_name = interface.interface
            serial_number = interface.serial_number
            manufacturer = interface.manufacturer

            for cls in MotorBus.can_types():
                bitrate_candidates = _get_allowed_baudrates_for(cls)
                if bitrate_candidates is None:
                    continue
                found = False
                for br in bitrate_candidates:
                    bus = None
                    try:
                        bus = MotorBus.create(cls, if_name, br)
                        if not bus.connect():
                            try:
                                bus.disconnect()
                            except Exception:
                                pass
                            continue
                        motors = bus.scan_motors()
                        if motors:
                            logger.info(f"Found motors on {if_name} using {cls.__name__} @ {br}")
                            motors_snapshot = dict(getattr(bus, "motors", {}))
                            try:
                                bus.disconnect()
                            except Exception:
                                pass

                            BusProxy = type(cls.__name__, (), {})
                            bus_proxy = BusProxy()
                            bus_proxy.interface = if_name
                            bus_proxy.baud_rate = br
                            bus_proxy.motors = motors_snapshot

                            results.append((bus_proxy, serial_number, manufacturer))
                            found = True
                            break
                        else:
                            try:
                                bus.disconnect()
                            except Exception:
                                pass
                    except Exception as e:
                        logger.debug(f"Error probing {cls} on {if_name} @ {br}: {e}")
                        if bus is not None:
                            try:
                                bus.disconnect()
                            except Exception:
                                pass
                if found:
                    break

        return results

    def get_pending_devices(self) -> list[Robot]:
        """Return a list of `Robot` objects representing motorbuses with motors attached.

        Converts each motorbus tuple returned by `_discover_motor_buses()` into a
        `Robot` object following the rules provided by the caller:
        - `id`: a generated UUID (persisted id) — serial number is stored on the connection
        - `name`: f"Unknown device on {motorbus.interface}"
        - `status`: DeviceStatus.AVAILABLE
        - `manufacturer`: None
        - `labels`: empty dict
        - `created_at`: datetime.now()
        - `is_transient`: True when serial number is missing
        - `calibration_settings`, `custom_protection_settings`: empty dicts
        - `motor_bus_connections`: {"motorbus": MotorBusConnection(...)}
        - `definition`: RobotDefinition with id="", display_name="Custom Robot Device",
          `description` aggregated from motor variants/models, and a single
          MotorBusDefinition under key "motorbus" containing per-motor entries
        """
        from datetime import datetime

        pending: list[Robot] = []
        results = self._discover_motor_buses()

        for bus, serial_number, _manufacturer in results:
            # Use a random UUID as the persisted robot id; serial is captured on the connection
            from uuid import uuid4

            robot_id = uuid4().hex
            name = f"Unknown device on {bus.interface}"
            status = DeviceStatus.AVAILABLE
            labels: dict = {}
            created_at = datetime.now()
            is_transient = not bool(serial_number)

            # MotorBus connection entry (serial_number may be None)
            baud_raw = getattr(bus, "baud_rate", None)
            baud_val = int(baud_raw) if baud_raw is not None else 0
            conn = RobotMotorBusConnection(
                motor_bus_type=bus.__class__.__name__,
                interface=bus.interface,
                baudrate=baud_val,
                serial_number=serial_number,
            )
            motor_bus_connections = {"motorbus": conn}

            # Build motor definitions (dict keyed by logical name) and type counts for description
            motor_defs: dict[str, RobotMotorDefinition] = {}
            type_counts: dict[str, int] = {}
            idx = 1
            for motor_key, entry in bus.motors.items():
                # entry is (driver, MotorModelInfo|None)
                # type: ignore[assignment]
                driver, minfo = entry  # type: ignore[assignment]
                name_idx = str(idx)
                idx += 1
                if minfo is not None and minfo.brand is not None:
                    brand = str(minfo.brand.value)
                else:
                    brand = minfo.model if minfo else ""

                model = minfo.model if (minfo and getattr(minfo, "model", None)) else ""
                variant = minfo.variant if (minfo and getattr(minfo, "variant", None)) else None

                motor_def = RobotMotorDefinition(
                    name=name_idx,
                    id=motor_key,
                    brand=str(brand),
                    model=str(model),
                    variant=variant,
                    need_calibration=True,
                )
                motor_defs[name_idx] = motor_def

                type_key = variant or model or "Unknown"
                type_counts[type_key] = type_counts.get(type_key, 0) + 1

            # Build description string like "4 STS3215-C001, 2 STS3215-C046"
            desc_parts = [f"{cnt} {typ}" for typ, cnt in type_counts.items()]
            description = ", ".join(desc_parts)

            # Construct MotorBusDefinition and RobotDefinition
            mb_def = MotorBusDefinition(
                type=bus.__class__.__name__,
                motors=motor_defs,
                baud_rate=getattr(bus, "baud_rate", None),
                interface_type=None,
            )
            rdef = RobotDefinition(
                id="",
                lerobot_name=None,
                display_name="Custom Robot Device",
                description=description,
                support_version_from=None,
                support_version_end=None,
                urdf=None,
                motor_buses={"motorbus": mb_def},
            )

            robot = Robot(
                id=robot_id,
                name=name,
                status=status,
                manufacturer=None,
                labels=labels,
                created_at=created_at,
                is_transient=is_transient,
                definition=rdef,
                calibration_settings={},
                custom_protection_settings={},
                motor_bus_connections=motor_bus_connections,
            )

            pending.append(robot)

        return pending

    def _motor_bus_verify(self, bus: "MotorBus", motorbus_def: MotorBusDefinition) -> bool:
        """Verify whether a MotorBus instance matches a given MotorBusDefinition.

        Checks performed:
          - bus class name equals motorbus_def.type
          - number of motors matches
          - for each motor in the definition, an entry exists on the bus with matching
            id, brand, model and (optionally) variant. If a definition's variant is None
            the variant is not compared.
        """
        try:
            # Type check on class name
            if bus.__class__.__name__ != motorbus_def.type:
                return False

            # Build definition dict keyed by the raw id values (coerce list ids to tuples for hashability)
            req_by_id: dict[object, RobotMotorDefinition] = {}
            # motorbus_def.motors is expected to be a dict[name -> RobotMotorDefinition]
            for req in motorbus_def.motors.values() if isinstance(motorbus_def.motors, dict) else motorbus_def.motors:
                # Use the motor definition's canonical key form (int or tuple).
                rid = getattr(req, "key", req.id)
                req_key = rid if not isinstance(rid, list) else tuple(rid)
                # Duplicate definition ids are ambiguous
                if req_key in req_by_id:
                    return False
                req_by_id[req_key] = req

            from typing import cast

            from leropilot.services.hardware.motor_drivers.base import BaseMotorDriver

            # Build bus dict keyed by the raw motor keys (coerce list keys to tuples)
            bus_by_id: dict[object, tuple[BaseMotorDriver[Any], MotorModelInfo | None]] = {}
            for k, entry in bus.motors.items():
                # Normalize list keys to tuples
                key_norm = tuple(k) if isinstance(k, list) else k
                if not entry:
                    return False
                driver, minfo = entry  # type: ignore[assignment]
                if minfo is None:
                    return False
                # Duplicate keys are ambiguous
                if key_norm in bus_by_id:
                    return False
                bus_by_id[key_norm] = cast(tuple[BaseMotorDriver[Any], MotorModelInfo | None], entry)

            # Counts must match
            if len(bus_by_id) != len(req_by_id):
                return False

            # Compare each required motor against discovered motor info using exact-key matching
            from typing import cast

            for rk, req in req_by_id.items():
                req_key = cast(int | tuple[int, int], rk)
                entry_val = bus_by_id.get(req_key)
                if entry_val is None:
                    return False
                driver, minfo = cast(tuple[BaseMotorDriver[Any], MotorModelInfo | None], entry_val)
                if minfo is None:
                    return False

                # Brand check (case-insensitive) — discovery must provide brand and it
                # must match the requirement. Compare using enum .value for clarity.
                if str(getattr(minfo, "brand").value).lower() != str(req.brand).lower():
                    return False

                # Model check (case-insensitive exact)
                if (getattr(minfo, "model", "") or "").lower() != str(req.model).lower():
                    return False

                # Variant check only when requirement specifies one
                if req.variant is not None:
                    if (getattr(minfo, "variant", "") or "").lower() != str(req.variant).lower():
                        return False

            return True
        except Exception:
            return False

    def _check_robot_status(
        self, robot: Robot, discovered: list[tuple["MotorBus", "str | None", "str | None"]]
    ) -> tuple[DeviceStatus, bool]:
        """Compare a persisted `robot` against `discovered` motorbuses and return
        the computed DeviceStatus and a boolean indicating whether the robot should
        be removed (transient and offline).

        Returns:
            (status, should_remove)
        """
        try:
            all_connections_ok = True
            any_mismatch = False

            # If robot has no motor_bus_connections, consider it offline/invalid
            if not robot.motor_bus_connections:
                return DeviceStatus.OFFLINE, robot.is_transient

            # For each connection, try to find a matching discovered bus
            for conn_key, conn in (robot.motor_bus_connections or {}).items():
                conn_found = False
                matched_bus = None
                for bus, serial_num, _mf in discovered:
                    # If conn has serial_number, prefer matching by serial
                    if conn.serial_number:
                        if conn.serial_number == serial_num:
                            conn_found = True
                            matched_bus = bus
                            break
                    else:
                        # Fall back to matching by interface (runtime info)
                        if conn.interface and getattr(bus, "interface", None) == conn.interface:
                            conn_found = True
                            matched_bus = bus
                            break

                if not conn_found:
                    # Could not find required motorbus -> offline
                    all_connections_ok = False
                    break

                # If we have a motorbus definition for this connection, verify it
                mb_def = None
                defn = robot.definition
                if isinstance(defn, str):
                    spec = RobotSpecService()
                    defn = spec.get_robot_definition(defn)
                    if defn is None:
                        all_connections_ok = False
                        break

                if defn and getattr(defn, "motor_buses", None):
                    try:
                        mb_def = defn.motor_buses.get(conn_key)
                    except Exception:
                        mb_def = None

                if mb_def is not None:
                    assert matched_bus is not None
                    ok = self._motor_bus_verify(matched_bus, mb_def)
                    if not ok:
                        any_mismatch = True

            # Apply status logic (same semantics as previous inlined code)
            if not all_connections_ok:
                return DeviceStatus.OFFLINE, robot.is_transient
            if any_mismatch:
                return DeviceStatus.INVALID, False
            return DeviceStatus.AVAILABLE, False
        except Exception:
            # On unexpected error, degrade to OFFLINE and keep robot if not transient
            return DeviceStatus.OFFLINE, robot.is_transient

    def verify_robot(self, robot: Robot) -> bool:
        """Verify a persisted `robot` against the actual motorbuses present.

        Constructs MotorBus objects for each `RobotMotorBusConnection` in
        `robot.motor_bus_connections`, runs `scan_motors()` on each bus to
        discover attached motors, and then delegates to `_check_robot_status`
        to compute the overall status.

        Raises:
            RobotVerificationError: when a required interface is missing, when the motorbus
                        type cannot be resolved, or when verification fails
                        resulting in OFFLINE or INVALID status.

        Returns:
            True on successful verification (AVAILABLE).
        """
        from leropilot.services.hardware.motor_buses.motor_bus import MotorBus

        if not robot.motor_bus_connections:
            raise ValueError("Robot has no motor bus connections to verify")

        discovered: list[tuple[MotorBus, str | None, str | None]] = []
        buses_to_close: list[MotorBus] = []

        try:
            for conn_key, conn in (robot.motor_bus_connections or {}).items():
                # Interface must be present to construct the runtime motorbus
                if not conn.interface:
                    raise RobotVerificationError(f"Interface for connection '{conn_key}' does not exist")

                # Resolve bus class
                try:
                    cls = MotorBus.resolve_bus_class(conn.motor_bus_type)
                except Exception as e:
                    raise RobotVerificationError(f"Unknown motorbus type '{conn.motor_bus_type}': {e}") from e

                # Create and probe the motorbus
                try:
                    bus = MotorBus.create(cls, conn.interface, conn.baudrate or 0)
                    if not bus.connect():
                        try:
                            bus.disconnect()
                        except Exception:
                            pass
                        raise RobotVerificationError(f"Unable to connect to motorbus on interface '{conn.interface}'")

                    buses_to_close.append(bus)
                    # scan_motors should populate bus.motors
                    bus.scan_motors()
                    discovered.append((bus, conn.serial_number, None))
                except ValueError:
                    # pass through ValueError for better user messages
                    raise
                except Exception as e:
                    try:
                        bus.disconnect()
                    except Exception:
                        pass
                    raise RuntimeError(f"Error probing motorbus '{conn_key}': {e}") from e

            # Use the helper to check computed status
            status, _should_remove = self._check_robot_status(robot, discovered)

            if status == DeviceStatus.OFFLINE:
                raise RobotVerificationError("Robot verification failed: robot is offline")
            if status == DeviceStatus.INVALID:
                raise RobotVerificationError("Robot verification failed: robot is invalid (mismatch)")

            # AVAILABLE -> verification passed
            return True
        finally:
            # Ensure buses are disconnected
            for b in buses_to_close:
                try:
                    b.disconnect()
                except Exception:
                    pass

    def refresh_status(self, robot_id: str | None = None) -> list[Robot] | Robot | None:
        """Refresh online/status state for a robot or all robots.

        Args:
            robot_id: Optional robot id to refresh (otherwise refresh all)

        Returns:
            If robot_id is None, returns list[Robot] of current robots after refresh.
            If robot_id is provided, returns the Robot instance after refresh, or
            None if the robot was transient and removed during refresh.
        """
        # Determine subset of robots to process
        to_process: list[tuple[str, Robot]] = []
        if robot_id is not None:
            r = self._robots.get(robot_id)
            if r is None:
                return None
            to_process = [(robot_id, r)]
        else:
            to_process = list(self._robots.items())

        # Aggregate filters (motorbus type, baudrate) from robots we will inspect
        filters: list[tuple[str, int | None]] = []
        for _rid, robot in to_process:
            defn = robot.definition
            if isinstance(defn, str):
                raise ValueError("Robot.definition must be a RobotDefinition, not a string")
            if not defn or not getattr(defn, "motor_buses", None):
                continue
            for key, _conn in (robot.motor_bus_connections or {}).items():
                mb = None
                try:
                    mb = defn.motor_buses.get(key)
                except Exception:
                    mb = None
                if mb is None:
                    continue
                filters.append((mb.type, mb.baud_rate or 0))

        # Discover available motorbuses (restrict by filters for efficiency)
        discovered = self._discover_motor_buses(filters if filters else None)

        # Map discovered (bus, serial, manufacturer) into lists for matching
        # We will iterate robots and try to match each of their connections
        removed_ids: list[str] = []
        for rid, robot in to_process:
            # Use helper to check robot status against discovered motorbuses
            new_status, should_remove = self._check_robot_status(robot, discovered)

            if new_status == DeviceStatus.OFFLINE and should_remove:
                # Robot is transient and offline -> remove
                removed_ids.append(rid)
            else:
                robot.status = new_status

        # Note: discovered buses were proxies (disconnected) created by _discover_motor_buses

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






# Robot URDF manager
class RobotUrdfManager:
    """Manager for robot URDF files and archives."""

    def __init__(self, robot_manager: RobotManager | None = None) -> None:
        self._robot_manager = robot_manager or get_robot_manager()

    def _get_robots_dir(self) -> Path:
        from leropilot.services.config.manager import get_config

        cfg = get_config()
        data_dir = Path(cfg.paths.data_dir)
        robots_dir = data_dir / "hardwares" / "robots"
        robots_dir.mkdir(parents=True, exist_ok=True)
        return robots_dir

    def _get_urdf_file(self, robot_id: str) -> Path:
        """Internal helper returning the expected custom URDF file path for a robot.

        Note: this returns the canonical path where a custom URDF would be stored;
        it does not guarantee the file exists. Callers should check existence.
        """
        robots_dir = self._get_robots_dir()
        return robots_dir / robot_id / "urdf" / "robot.urdf"

    def delete_custom_urdf(self, robot_id: str) -> None:
        """Delete a previously uploaded custom URDF and any related resource files.

        Raises:
            ValueError: if the robot does not exist.
            FileNotFoundError: if no custom URDF is present on disk.
            RuntimeError: for other failures during deletion.
        """
        robot = self._robot_manager.get_robot(robot_id)
        if robot is None:
            raise ValueError("Robot not found")
        urdf_file = self._get_urdf_file(robot_id)
        if not urdf_file.exists():
            raise FileNotFoundError("Custom URDF not found")

        # Remove the entire urdf directory tree for this robot
        urdf_dir = urdf_file.parent
        import shutil

        try:
            shutil.rmtree(urdf_dir)
            # If robot dir is empty after removal, remove it as well
            robot_dir = urdf_dir.parent
            try:
                if robot_dir.exists() and not any(robot_dir.iterdir()):
                    robot_dir.rmdir()
            except Exception:
                # Ignore failures to remove parent dir
                pass
        except Exception as e:
            raise RuntimeError(f"Failed to delete URDF: {e}") from e

    def upload_custom_urdf(self, robot_id: str, data: bytes) -> Path:
        import io
        import os
        import shutil
        import tarfile
        import tempfile
        import zipfile

        # Basic validation
        robot = self._robot_manager.get_robot(robot_id)
        if robot is None:
            raise ValueError("Robot not found")
        if getattr(robot, "category", DeviceCategory.ROBOT) != DeviceCategory.ROBOT:
            raise ValueError("URDFs can only be uploaded for robots")

        target_dir = self._get_robots_dir() / robot_id / "urdf"
        target_dir.mkdir(parents=True, exist_ok=True)

        def _validate_and_mark(urdf_file: Path) -> None:
            from leropilot.utils.urdf import validate_file

            result = validate_file(str(urdf_file))
            if not result.get("valid", False):
                raise ValueError({"error": "URDF validation failed", "details": result})

            # Validation passed; custom URDF file is present on disk (no flag required)

        if data.startswith(b"PK"):
            try:
                with zipfile.ZipFile(io.BytesIO(data)) as zf:
                    names = [n for n in zf.namelist() if not n.endswith("/")]
                    top_urdfs = [
                        n
                        for n in names
                        if os.path.basename(n).lower().endswith(".urdf") and ("/" not in n and "\\" not in n)
                    ]
                    if len(top_urdfs) != 1:
                        raise ValueError("Archive must contain exactly one top-level .urdf file")
                    with tempfile.TemporaryDirectory() as tmpd:
                        zf.extractall(tmpd)
                        for root, _dirs, files in os.walk(tmpd):
                            rel_root = os.path.relpath(root, tmpd)
                            dest_root = target_dir if rel_root == "." else target_dir / rel_root
                            dest_root.mkdir(parents=True, exist_ok=True)
                            for fname in files:
                                src = Path(root) / fname
                                dest = dest_root / fname
                                shutil.move(str(src), str(dest))

                        top_urdf_name = top_urdfs[0]
                        src_urdf = target_dir / os.path.basename(top_urdf_name)
                        dest_urdf = target_dir / "robot.urdf"
                        if not src_urdf.exists():
                            raise ValueError("Top-level URDF not found after extraction")
                        if src_urdf.name != "robot.urdf":
                            try:
                                dest_urdf.unlink(missing_ok=True)
                            except Exception:
                                pass
                            shutil.move(str(src_urdf), str(dest_urdf))

                        _validate_and_mark(dest_urdf)
                        return dest_urdf
            except ValueError:
                raise
            except Exception as e:
                raise ValueError(f"Failed to process ZIP archive: {e}") from e
        elif data[:2] == b"\x1f\x8b":
            try:
                with tempfile.TemporaryDirectory() as tmpd:
                    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tf:
                        members = [m for m in tf.getmembers() if m.isfile()]
                        top_urdfs = [
                            m.name
                            for m in members
                            if os.path.basename(m.name).lower().endswith(".urdf")
                            and ("/" not in m.name and "\\" not in m.name)
                        ]
                        if len(top_urdfs) != 1:
                            raise ValueError("Archive must contain exactly one top-level .urdf file")
                        tf.extractall(tmpd)
                        for root, _dirs, files in os.walk(tmpd):
                            rel_root = os.path.relpath(root, tmpd)
                            dest_root = target_dir if rel_root == "." else target_dir / rel_root
                            dest_root.mkdir(parents=True, exist_ok=True)
                            for fname in files:
                                src = Path(root) / fname
                                dest = dest_root / fname
                                shutil.move(str(src), str(dest))

                                src_urdf = target_dir / os.path.basename(top_urdfs[0])
                        dest_urdf = target_dir / "robot.urdf"
                        if not src_urdf.exists():
                            raise ValueError("Top-level URDF not found after extraction")
                        if src_urdf.name != "robot.urdf":
                            try:
                                dest_urdf.unlink(missing_ok=True)
                            except Exception:
                                pass
                            shutil.move(str(src_urdf), str(dest_urdf))

                        _validate_and_mark(dest_urdf)
                        return dest_urdf
            except ValueError:
                raise
            except Exception as e:
                raise ValueError(f"Failed to process tar.gz archive: {e}") from e
        else:
            try:
                dest_urdf = target_dir / "robot.urdf"
                with open(dest_urdf, "wb") as fh:
                    fh.write(data)
                _validate_and_mark(dest_urdf)
                return dest_urdf
            except Exception as e:
                raise ValueError(f"Failed to save URDF: {e}") from e

    def get_robot_urdf_resource(self, robot_id: str, path: str = "robot.urdf") -> bytes | None:
        """Return the bytes content of a URDF file for a robot.

        Args:
            robot_id: persisted robot id
            path: resource path/filename to look up (defaults to "robot.urdf").

        Returns:
            `bytes` when a resource is found and read, or `None` when not found.

        Raises:
            ValueError: if the robot is not found.
        """
        # Local imports to avoid import cycles and keep module-level imports light
        from importlib.abc import Traversable
        from leropilot.utils.urdf import get_robot_resource

        robot = self._robot_manager.get_robot(robot_id)
        if robot is None:
            raise ValueError("Robot not found")

        # Check custom user-provided resources first
        urdf_dir = self._get_urdf_file(robot_id).parent
        user_file = urdf_dir / path
        if user_file.exists():
            try:
                return user_file.read_bytes()
            except Exception as e:
                raise RuntimeError(f"Failed to read custom URDF: {e}") from e

        # Resolve default via robot.definition.id (preferred over lerobot_name for resources)
        defn = robot.definition
        if isinstance(defn, str):
            raise ValueError("Robot.definition must be a RobotDefinition, not a string")
        # If there's no definition, there is no built-in URDF
        if not defn:
            return None
        
        # Use definition ID as the resource folder name
        resource = get_robot_resource(defn.id, path)
            
        if resource:
            # Use as_file to get a filesystem path to read from
            try:
                with importlib.resources.as_file(resource) as fp:
                    return fp.read_bytes()
            except Exception as e:
                raise RuntimeError(f"Failed to read packaged URDF: {e}") from e

        return None

# Convenience getters
_robot_manager: RobotManager | None = None
_manager_lock = threading.Lock()


def get_robot_manager() -> RobotManager:
    global _robot_manager
    with _manager_lock:
        if _robot_manager is None:
            _robot_manager = RobotManager()
        return _robot_manager


# Singleton accessor for URDF manager
_robot_urdf_manager: RobotUrdfManager | None = None
_urdf_lock = threading.Lock()


def get_robot_urdf_manager() -> RobotUrdfManager:
    global _robot_urdf_manager
    with _urdf_lock:
        if _robot_urdf_manager is None:
            _robot_urdf_manager = RobotUrdfManager()
        return _robot_urdf_manager
