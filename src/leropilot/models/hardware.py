"""Hardware related models."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, field_validator, model_validator

# Hardware Device Management Models


class DeviceCategory(str, Enum):
    """Device category classification."""

    ROBOT = "robot"  # Execution devices (follower arms)
    CONTROLLER = "controller"  # Input devices (leader arms, gamepads)
    CAMERA = "camera"  # Vision devices (RGB, depth cameras)


class DeviceStatus(str, Enum):
    """Real-time device availability status."""

    AVAILABLE = "available"  # Device connected and ready
    OFFLINE = "offline"  # Device not physically connected
    OCCUPIED = "occupied"  # Device in use by another process
    INVALID = "invalid"  # Device config does not match actual hardware (mismatch)


class MotorBrand(str, Enum):
    """Supported motor protocols/brands."""

    DYNAMIXEL = "dynamixel"
    FEETECH = "feetech"
    DAMIAO = "damiao"


class InterfaceType(str, Enum):
    """Communication interface types."""

    SERIAL = "serial"
    CAN = "can"
    SLCAN = "slcan"  # Serial-to-CAN adapter


class RobotMotorBusConnection(BaseModel):
    """Connection info for a robot's motor bus.

    This model is persisted as part of a Robot entry in list.json, and
    includes an optional `serial_number` that ties a persisted robot to a
    specific physical motorbus when available. The `interface` field may be
    present at runtime but is not considered part of the persisted identity
    (serial_number serves that purpose)."""

    motor_bus_type: str
    interface: str | None
    baudrate: int
    serial_number: str | None = None


class Robot(BaseModel):
    """Base robot model stored in list.json (replaces Device)."""

    id: str = Field(..., description="Unique serial number from hardware")
    name: str = Field(..., description="User-friendly robot name")
    status: DeviceStatus = Field(DeviceStatus.OFFLINE, description="Runtime robot status")
    manufacturer: str | None = Field(None, description="Manufacturer from discovery (read-only)")
    labels: dict[str, str] = Field(default_factory=dict, description="Key-value labels for automation")
    created_at: datetime = Field(default_factory=datetime.now)

    # Persisted fields
    is_transient: bool = Field(False, description="If true, robot should not be persisted to disk")
    definition: "RobotDefinition | str | None" = Field(None, description="Robot definition or definition id")
    calibration_settings: dict[str, list["MotorCalibration"]] = Field(default_factory=dict, description="Per-motor-bus calibration lists; key=bus name")
    custom_protection_settings: dict[tuple[str, str, str | None], list["MotorLimit"]] = Field(
        default_factory=dict,
        description=(
            "Custom protection settings keyed by motor (brand, model, variant) -> [MotorLimit]. "
            "Variant may be None to apply to all variants of a model."
        ),
    )


    # Connection info for motor buses (persisted as part of the Robot entry).
    # `interface` may be present at runtime but is not required to be persisted.
    motor_bus_connections: dict[str, RobotMotorBusConnection] | None = Field(None, description="Motor bus connection info; persisted with robot entry")

    class Config:
        use_enum_values = True

    @model_validator(mode="after")
    def _normalize_custom_protection_settings(self):
        """Normalize keys in `custom_protection_settings` to canonical tuples

        Accepts keys as:
        - tuples/lists of (brand, model) or (brand, model, variant)
        - colon-separated strings 'brand:model' or 'brand:model:variant'

        Normalizes all keys to `(brand, model, variant|None)`.
        """
        new: dict[tuple[str, str, str | None], list[MotorLimit]] = {}
        for k, v in self.custom_protection_settings.items():
            brand: str | None = None
            model: str | None = None
            variant: str | None = None

            if isinstance(k, str):
                parts = k.split(":")
                if len(parts) >= 2:
                    brand = parts[0]
                    model = parts[1]
                    variant = parts[2] if len(parts) >= 3 else None
                else:
                    raise ValueError("custom_protection_settings keys must be 'brand:model' or 'brand:model:variant' when provided as strings")
            elif isinstance(k, (list, tuple)):
                if len(k) == 2:
                    brand, model = str(k[0]), str(k[1])
                    variant = None
                elif len(k) >= 3:
                    brand, model, variant = str(k[0]), str(k[1]), str(k[2])
                else:
                    raise ValueError("custom_protection_settings keys must be (brand, model) or (brand, model, variant)")
            elif isinstance(k, tuple) and len(k) in (2, 3):
                brand, model = str(k[0]), str(k[1])
                variant = str(k[2]) if len(k) == 3 else None
            else:
                raise ValueError("Unsupported custom_protection_settings key type")

            new_key = (brand, model, variant)
            new[new_key] = v

        object.__setattr__(self, "custom_protection_settings", new)
        return self






class PlatformSerialPort(BaseModel):
    """Platform-level serial port discovery result.

    Backend implementations should return a list of these objects instead of raw
    dictionaries to provide a stable, typed interface to callers.
    """

    port: str
    description: str | None = None
    hwid: str | None = None
    serial_number: str | None = None
    manufacturer: str | None = None
    vid: str | None = None
    pid: str | None = None


class PlatformCANInterface(BaseModel):
    """Platform-level CAN interface discovery result.

    Includes interface id (e.g., "can0", "pcan:PCAN_USBBUS1") and optional
    metadata such as manufacturer and serial number.
    """

    interface: str
    state: str | None = None
    manufacturer: str | None = None
    product: str | None = None
    vid: str | None = None
    pid: str | None = None
    serial_number: str | None = None




class ProtectionViolation(BaseModel):
    """Motor protection parameter violation."""

    type: str = Field(..., description="Violation type (e.g., temp_warning, voltage_low)")
    value: float = Field(..., description="Current value")
    limit: float = Field(..., description="Threshold limit")


class ProtectionStatus(BaseModel):
    """Motor protection status."""

    status: str = Field(..., description="ok | warning | critical")
    violations: list[ProtectionViolation] = Field(default_factory=list)


class MotorTelemetry(BaseModel):
    """Real-time motor telemetry data (all values in SI units)."""

    id: int
    position: float = Field(..., description="Position in radians")
    velocity: float = Field(..., description="Velocity in rad/s")
    current: int = Field(..., description="Current in mA")
    load: int = Field(..., description="Load percentage (0-100)")
    temperature: int = Field(..., description="Temperature in °C")
    voltage: float = Field(..., description="Voltage in V")
    moving: bool = Field(..., description="Is motor currently moving")
    goal_position: float = Field(..., description="Target position in radians")
    error: int = Field(0, description="Hardware error flags")
    protection_status: ProtectionStatus = Field(default_factory=lambda: ProtectionStatus(status="ok"))




class MotorCalibration(BaseModel):
    """Motor calibration data (compatible with lerobot format).

    NOTE: `id` field renamed to `name` (string) to identify motor by name within a bus.
    """

    name: str = Field(..., description="Motor name on the bus (e.g., joint name)")
    drive_mode: int = Field(0, description="0 = normal, 1 = inverted direction")
    homing_offset: int = Field(..., description="Encoder offset for zero position (raw units)")
    range_min: int = Field(..., description="Minimum position limit (raw encoder units)")
    range_max: int = Field(..., description="Maximum position limit (raw encoder units)")


# Deprecated: Use `MotorModelInfo` and `MotorLimit` instead of this legacy structure.
# Retained for backward compatibility with `motor_specs.json` handling.
class MotorProtectionParams(BaseModel):
    """Motor protection parameters.

    Deprecated: prefer `MotorModelInfo` + `MotorLimit` for new code. This class mirrors
    the historical `motor_specs.json` layout and is kept for compatibility until
    migrations are completed. Fields are optional to allow conversion from partial
    table-based `MotorModelInfo` entries during migration.
    """

    model_ids: list[int] = Field(default_factory=list, description="Possible model IDs for detection")
    temp_warning: int | None = Field(None, description="Warning temperature threshold (°C)")
    temp_critical: int | None = Field(None, description="Critical temperature threshold (°C)")
    temp_max: int | None = Field(None, description="Absolute max temperature from datasheet (°C)")
    voltage_min: float | None = Field(None, description="Minimum safe voltage (V)")
    voltage_max: float | None = Field(None, description="Maximum safe voltage (V)")
    current_max: int | None = Field(None, description="Maximum continuous current (mA)")
    current_peak: int | None = Field(None, description="Peak current limit (mA)")
    datasheet_url: str | None = Field(None, description="Link to motor datasheet")


# ============================================================================
# Motor Protection Database
# ============================================================================




# Common limit type constants (canonical names)
LIMIT_VOLTAGE_MIN = "voltage_min"
LIMIT_VOLTAGE_MAX = "voltage_max"
LIMIT_CURRENT_MAX_MA = "current_max_ma"
LIMIT_TEMPERATURE_MAX_C = "temperature_max_c"
LIMIT_TORQUE_MAX_NM = "torque_max_nm"


class MotorLimit(BaseModel):
    """Flexible single limit entry.

    Use `type` as the canonical key for the limit (e.g., 'voltage_min', 'current_max_ma').

    This class defines common limit type constants to centralize naming and avoid
    module-level scatter. Prefer module-level `LIMIT_*` constants where possible.
    """

    # Convenience list of common limits
    COMMON_LIMIT_TYPES: list[str] = [
        LIMIT_VOLTAGE_MIN,
        LIMIT_VOLTAGE_MAX,
        LIMIT_CURRENT_MAX_MA,
        LIMIT_TEMPERATURE_MAX_C,
        LIMIT_TORQUE_MAX_NM,
    ]

    type: str = Field(..., description="Limit type identifier, e.g., 'voltage_min'")
    value: float = Field(..., description="Limit value in SI units (float)")


class MotorModelInfo(BaseModel):
    """Combined model/variant metadata for a motor model.

    - Uses Pydantic for runtime validation and serialization.
    - `model_ids` is required (model identification depends on it).
    - `limits` is required and should be defined directly in per-protocol tables (not injected from JSON).

    Note: `brand` is required and should specify the motor protocol family (e.g., DYNAMIXEL, FEETECH, DAMIAO).
    """

    model: str
    model_ids: list[int] = Field(..., description="Numeric model identifiers associated with this model/variant")
    limits: dict[str, MotorLimit] = Field(..., description="Mapping of limit-type -> MotorLimit (SI units)")

    variant: str | None = None
    description: str | None = None

    brand: "MotorBrand" = Field(..., description="Motor brand/protocol family (e.g., DYNAMIXEL, FEETECH, DAMIAO)")

    # Conversion/encoding helpers
    encoder_resolution: int | None = None
    position_scale: float | None = None
    encoding: str | None = None
    endianness: str | None = None
    gear_ratio: float | None = None
    direction_inverted: bool | None = None

    # Protocol references (point to shared objects in protocol tables)
    baudrates: list[int] | None = None
    # operating_modes recommended to be an Enum in driver code; stored here as string/int codes
    operating_modes: list[str] | None = None
    registries: dict | None = None


# Deprecated module-level aliases for common limit names.
# Prefer `MotorLimit.LIMIT_*` constants; these aliases are kept for
# backward-compatibility and will be removed in a future release.
class MotorLimitTypes:
    """Container for canonical motor limit names.

    These are plain string constants used as keys in `MotorModelInfo.limits`.
    Keep this class simple and importable without pulling in Pydantic models to
    avoid import-time side effects.
    """

    VOLTAGE_MIN: str = "voltage_min"
    VOLTAGE_MAX: str = "voltage_max"
    CURRENT_MAX_MA: str = "current_max_ma"
    TEMPERATURE_MAX_C: str = "temperature_max_c"
    TORQUE_MAX_NM: str = "torque_max_nm"

    COMMON_LIMIT_TYPES: list[str] = [
        VOLTAGE_MIN,
        VOLTAGE_MAX,
        CURRENT_MAX_MA,
        TEMPERATURE_MAX_C,
        TORQUE_MAX_NM,
    ]


class MotorProtectionOverride(BaseModel):
    """User custom motor protection overrides"""

    source: str = Field("builtin", description="'builtin' or 'custom'")
    overrides: dict[str, float] | None = None  # e.g., {"temp_warning": 55}


class DeviceProtection(BaseModel):
    """Protection configuration for a device"""

    temp_limit: int = 60
    voltage_min: float = 10.0
    overrides: dict[str, float] = Field(default_factory=dict)
    # We can also store per-motor overrides if needed


class MotorConfig(BaseModel):
    """Configuration for a single motor."""

    calibration: MotorCalibration | None = None
    protection: MotorProtectionOverride | None = None





# ============================================================================
# Robot Definitions (from robots.json)
# ============================================================================


class RobotMotorDefinition(BaseModel):
    """Motor requirement in a robot definition.

    - `name`: logical motor name (joint name) used as dict key in MotorBusDefinition. When loading from
      list-based specs, `name` will be derived from the motor's `id` if not provided.
    - `id`: input alias for the motor id. Internally we store the raw form (int or
      `(send, recv)` tuple) on `raw_id` for unambiguous access.

    Convenience properties exposed:
      - `id` (int): primary send id (always an int)
      - `recv_id` (int): receive id (equal to `id` when not distinct)
      - `key` (int | tuple): raw key used by drivers and verification (int or (send, recv)).

    - `need_calibration`: whether this motor requires calibration (default: True). Set to `false` in the
      specs to disable calibration for specific motors (e.g., wheels).
    """

    name: str | None = None
    raw_id: int | tuple[int, int] = Field(..., alias="id")
    brand: str
    model: str
    variant: str | None = None
    need_calibration: bool = Field(True, description="Whether the motor needs calibration")

    @field_validator("raw_id", mode="before")
    def _normalize_raw_id(cls, v):
        """Normalize list-style ids into int or tuple forms for `raw_id`.

        Accepts lists from JSON (e.g., `[1]` or `[1, 2]`) and converts them to an
        `int` or `tuple[int, int]` respectively. Rejects lists with length != 1 or 2.
        """
        if isinstance(v, list):
            if len(v) == 1:
                return int(v[0])
            if len(v) == 2:
                return (int(v[0]), int(v[1]))
            raise ValueError("id list must have length 1 or 2")
        return v

    @property
    def id(self) -> int:
        """Primary send id (int)."""
        raw = object.__getattribute__(self, "raw_id")
        return int(raw[0]) if isinstance(raw, tuple) else int(raw)

    @property
    def recv_id(self) -> int:
        """Receive id (int). Equal to `id` when not provided separately."""
        raw = object.__getattribute__(self, "raw_id")
        return int(raw[1]) if isinstance(raw, tuple) else int(raw)

    @property
    def key(self) -> int | tuple[int, int]:
        """Return the raw key form used for matching against drivers (int or tuple)."""
        return object.__getattribute__(self, "raw_id")



class MotorBusDefinition(BaseModel):
    """Motor bus definition within a robot.

    `motors` may be provided either as a dict keyed by logical motor name or as a
    list of motor definitions (as historically used in `robots.json`). When a list
    is provided the model will normalize it into a dict keyed by each motor's
    `name` (or by its `id` when `name` is not supplied).
    """

    type: str
    motors: dict[str, RobotMotorDefinition] | list[RobotMotorDefinition]
    baud_rate: int | None = None  # Serial baud rate or CAN bitrate
    interface_type: str | None = None  # serial, can, slcan, etc.

    @model_validator(mode="before")
    def _normalize_motors(cls, values: dict):
        """Normalize list-style `motors` into a dict keyed by motor name.

        Accepts raw dicts or list entries from JSON and ensures resulting value
        assigned to `motors` is a dict[str, RobotMotorDefinition]-like structure
        so callers and downstream code can rely on a consistent shape.
        """
        motors = values.get("motors")
        if motors is None:
            return values

        # If motors supplied as a list, convert to dict keyed by name (or id)
        if isinstance(motors, list):
            new: dict[str, object] = {}
            for idx, m in enumerate(motors, start=1):
                # m may be a mapping from JSON. Ensure 'name' present.
                if isinstance(m, dict):
                    name = m.get("name")
                    if not name:
                        # Prefer id as key when available, otherwise use index
                        mid = m.get("id")
                        name = str(mid) if mid is not None else str(idx)
                    m["name"] = name
                    new[name] = m
                else:
                    # Already parsed object (unlikely before validation)
                    name = getattr(m, "name", None) or str(getattr(m, "id", idx))
                    new[name] = m
            values["motors"] = new
            return values

        # If motors is a dict, ensure each entry has a 'name' set if it is a dict
        if isinstance(motors, dict):
            for k, v in list(motors.items()):
                if isinstance(v, dict) and "name" not in v:
                    v["name"] = k
                    motors[k] = v
            values["motors"] = motors
        return values




class RobotDefinition(BaseModel):
    """Robot configuration definition from robots.json."""

    id: str
    lerobot_name: str | None = None
    display_name: str | dict[str, str]
    description: str | dict[str, str]
    image: str | None = None
    support_version_from: str | None = None
    support_version_end: str | None = None
    urdf: str | None = None
    motor_buses: dict[str, MotorBusDefinition]


# ============================================================================
# Discovery Results
# ============================================================================





class CameraSummary(BaseModel):
    """Minimal camera summary returned by discovery and listing APIs."""

    index: int = Field(..., description="Camera index (0,1,...)")
    name: str = Field(..., description="Camera display name")
    width: int | None = Field(None, description="Reported frame width")
    height: int | None = Field(None, description="Reported frame height")
    available: bool = Field(True, description="Quick availability check (best-effort)")



# ============================================================================
# Motor Discovery Results
# ============================================================================


class SuggestedRobot(BaseModel):
    """Suggested robot configuration from robots.json match."""

    id: str
    lerobot_name: str
    display_name: str


class MotorDiscoverResult(BaseModel):
    """Result from motor discovery / probe operation"""

    interface: str
    interface_type: InterfaceType
    brand: MotorBrand
    baud_rate: int
    # Mapping from motor id -> MotorModelInfo discovered on the interface
    discovered_motors: dict[int, "MotorModelInfo"] = Field(default_factory=dict)
    suggested_robots: list[SuggestedRobot] = Field(default_factory=list)
    logs: list[str] = Field(default_factory=list)


# ============================================================================
# Motor Scan Results
# ============================================================================


class MotorScanResult(BaseModel):
    """Result from motor bus scan"""

    motors: dict[int, "MotorModelInfo"]
    suggested_robots: list[SuggestedRobot] | None = None
    scan_duration_ms: float


# ============================================================================
# Device Settings & Configuration
# ============================================================================






# ============================================================================
# All Motors Telemetry
# ============================================================================


