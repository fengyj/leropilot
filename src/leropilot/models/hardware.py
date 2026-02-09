"""Hardware related models."""

from datetime import datetime
from enum import Enum
from typing import Any, ClassVar, Literal

from pydantic import BaseModel, Field, RootModel, field_validator

# Type aliases for motor identification
MotorID = int | tuple[int, int]

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


class PositionType(str, Enum):
    """Types of motor position representations."""

    RAW = "raw"  # Direct hardware reading in encoder units
    CALIBRATED = "calibrated"  # Raw position adjusted by homing_offset (if soft_homing_offset=true)
    NORMALIZED = "normalized"  # Scaled to [-1, 1] range based on range_min/range_max
    RAW_IN_RADIAN = "raw_in_radian"  # Raw position converted to standardized radians using position_to_radian_ratio
    CALIBRATED_IN_RADIAN = "calibrated_in_radian"  # Calibrated position converted to standardized radians


class MotorNormMode(str, Enum):
    """Motor normalization modes for converting raw position values to normalized forms.

    These modes define how raw motor positions (bounded by range_min/range_max) are
    converted to normalized values for teleoperation and other applications.
    """

    RANGE_M100_100 = "range_m100_100"
    """Normalize to [-100, 100] range.

    Formula: normalized = (((raw - min) / (max - min)) * 200) - 100

    If drive_mode is enabled, the result is negated: -normalized
    """

    RANGE_0_100 = "range_0_100"
    """Normalize to [0, 100] range.

    Formula: normalized = ((raw - min) / (max - min)) * 100

    If drive_mode is enabled, the result is inverted: 100 - normalized
    """

    DEGREES = "degrees"
    """Convert to degrees relative to midpoint.

    Formula: normalized = (raw - mid) * 360 / max_res

    Where mid = (min + max) / 2 and max_res = encoder_resolution - 1

    This mode is useful for motors with a defined encoder resolution,
    providing intuitive degree-based control.
    """


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

    is_calibrated: bool = Field(False, description="Whether robot has been calibrated (required)")

    # Persisted fields
    is_transient: bool = Field(False, description="If true, robot should not be persisted to disk")
    definition: "RobotDefinition | str | None" = Field(None, description="Robot definition or definition id")
    calibration_settings: dict[str, list["MotorCalibration"]] = Field(
        default_factory=dict,
        description="Per-motor-bus calibration lists; key=bus name",
    )
    custom_protection_settings: dict[tuple[str, str, str | None], list["MotorLimit"]] = Field(
        default_factory=dict[tuple[str, str, str | None], list["MotorLimit"]],
        description=(
            "Custom protection settings keyed by motor (brand, model, variant) -> [MotorLimit]. "
            "Variant may be None to apply to all variants of a model."
        ),
    )

    # Connection info for motor buses (persisted as part of the Robot entry).
    # `interface` may be present at runtime but is not required to be persisted.
    motor_bus_connections: dict[str, RobotMotorBusConnection] | None = Field(
        None,
        description="Motor bus connection info; persisted with robot entry",
    )

    class Config:
        use_enum_values = True

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

    Includes interface id (e.g., "socketcan:can0", "pcan:PCAN_USBBUS1") and optional
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
    violations: list[ProtectionViolation] = Field(default_factory=list[ProtectionViolation])


class MotorTelemetry(BaseModel):
    """Real-time motor telemetry data.

    Position fields (position, goal_position) represent motor position in the unit
    specified by position_type. For raw positions, this is the native hardware unit
    (counts for Feetech/Dynamixel, radians for Damiao). For other types, positions
    are converted to calibrated or normalized forms at the MotorBus layer.

    When position_type is CALIBRATED or CALIBRATED_IN_RADIAN, position may be None
    if the motor has not been calibrated yet. Similarly, NORMALIZED requires
    calibration data to be available.
    """

    motor_id: MotorID
    position: float | None = Field(
        ...,
        description=(
            "Motor position in the unit specified by position_type (None if not available for this position_type)"
        ),
    )
    position_type: PositionType = Field(..., description="Unit/representation of position field")
    goal_position: float | None = Field(None, description="Last set position target in the same unit as position")

    velocity: float = Field(
        ..., description="Velocity in rad/s (converted from hardware units using velocity_ratio from MotorModelInfo)"
    )
    torque: float | None = Field(
        None,
        description="Torque in N·m (None if unavailable or estimated)",
    )
    current: float | None = Field(None, description="Current in mA (None if unavailable or estimated)")
    temperature: float | None = Field(None, description="Temperature in °C (None if unavailable)")
    voltage: float | None = Field(None, description="Voltage in V (None if unavailable)")
    moving: bool = Field(..., description="Is motor currently moving")
    error: int = Field(0, description="Hardware error flags")
    protection_status: ProtectionStatus = Field(default_factory=lambda: ProtectionStatus(status="ok"))

    # NOTE: Removed permissive conversion/auto-clamping validators in favor of explicit typing
    # and Field constraints. Drivers are expected to provide SI-unit floats where applicable.


class MotorBusData(BaseModel):
    """Motor bus telemetry data containing all motors on a single bus.

    Motors are indexed by their logical names (e.g., 'joint_1', 'gripper')
    as defined in the robot definition.
    """

    bus_name: str = Field(..., description="Motor bus identifier")
    motors: dict[str, MotorTelemetry] = Field(
        ..., description="Mapping from motor_name -> MotorTelemetry for all motors on this bus"
    )


class RobotTelemetryFrame(BaseModel):
    """Complete telemetry frame for a robot at a given timestamp.

    Contains telemetry from all motor buses, actual FPS, timestamp,
    and normalization flag.
    """

    timestamp: float = Field(..., description="Unix timestamp in seconds")
    motor_buses: dict[str, MotorBusData] = Field(..., description="Mapping from bus_name -> MotorBusData for all buses")
    actual_fps: int = Field(..., description="Actual achieved frames per second (rounded)")
    normalized: bool = Field(..., description="Whether position values are normalized to [-1, 1]")


class MotorCalibration(BaseModel):
    """Motor calibration data (compatible with lerobot format)."""

    name: str = Field(..., description="Motor name on the bus (e.g., joint name)")
    id: MotorID | None = Field(
        None,
        description="Motor protocol ID. int for Dynamixel/Feetech (1-254), tuple (send_id, recv_id) for Damiao CAN",
    )
    drive_mode: int = Field(0, description="0 = normal, 1 = inverted direction")
    norm_mode: "MotorNormMode" = Field(
        MotorNormMode.RANGE_M100_100,
        description=(
            "Normalization mode for this motor's calibration.\n"
            "Cannot be null; defaults to RANGE_M100_100 for backward compatibility."
        ),
    )
    homing_offset: float = Field(
        ..., description="Encoder offset for zero position (radians for Damiao, raw units for others)"
    )
    range_min: float = Field(
        ..., description="Minimum position limit (radians for Damiao, raw encoder units for others)"
    )
    range_max: float = Field(
        ..., description="Maximum position limit (radians for Damiao, raw encoder units for others)"
    )
    soft_homing_offset: bool = Field(..., description="Indicate should apply homing offset in software or not")


# Deprecated: Use `MotorModelInfo` and `MotorLimit` instead of this legacy structure.
# Retained for backward compatibility with `motor_specs.json` handling.
class MotorProtectionParams(BaseModel):
    """Motor protection parameters.

    Deprecated: prefer `MotorModelInfo` + `MotorLimit` for new code. This class mirrors
    the historical `motor_specs.json` layout and is kept for compatibility until
    migrations are completed. Fields are optional to allow conversion from partial
    table-based `MotorModelInfo` entries during migration.
    """

    model_ids: list[int] = Field(default_factory=list[int], description="Possible model IDs for detection")
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


# Note: canonical limit type names are now defined on `MotorLimit` as `LIMIT_*` constants.
# Module-level aliases for backward compatibility are kept below (assigned after `MotorLimit`).


class MotorLimit(BaseModel):
    """Flexible single limit entry.

    Use `type` as the canonical key for the limit (e.g., 'voltage_min', 'current_max_ma').

    This class is the authoritative place for canonical limit type names. Use
    `MotorLimit.LIMIT_*` constants when referring to limit types in code.
    """

    # Canonical string constants for common limit types (ClassVar so Pydantic won't treat them as fields)
    LIMIT_VOLTAGE_MIN: ClassVar[str] = "voltage_min"
    LIMIT_VOLTAGE_MAX: ClassVar[str] = "voltage_max"
    LIMIT_CURRENT_MAX_MA: ClassVar[str] = "current_max_ma"
    LIMIT_TEMPERATURE_MAX_C: ClassVar[str] = "temperature_max_c"
    LIMIT_TORQUE_MAX_NM: ClassVar[str] = "torque_max_nm"

    # Convenience list of common limits (derived from canonical constants)
    COMMON_LIMIT_TYPES: ClassVar[list[str]] = [
        LIMIT_VOLTAGE_MIN,
        LIMIT_VOLTAGE_MAX,
        LIMIT_CURRENT_MAX_MA,
        LIMIT_TEMPERATURE_MAX_C,
        LIMIT_TORQUE_MAX_NM,
    ]

    type: str = Field(..., description="Limit type identifier, e.g., 'voltage_min'")
    value: float = Field(..., description="Limit value in SI units (float)")


UnitType = Literal["position", "current", "velocity", "acceleration", "temperature", "voltage", "torque"]


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
    encoder_resolution: float = Field(
        ...,
        description=(
            "Encoder resolution (counts per full rotation).\n"
            "- Feetech (4096-count encoder): 4096.0\n"
            "- Dynamixel (4096-count encoder): 4096.0\n"
            "- Damiao: 65536.0"
        ),
    )
    position_to_radian_ratio: float = Field(
        ...,
        description=(
            "Multiplier to convert hardware position units to radians.\n"
            "- Feetech (4096-count encoder): (2π) / 4096\n"
            "- Dynamixel (4096-count encoder): (2π) / 4096\n"
            "- Damiao (native radians): 1.0"
        ),
    )
    velocity_ratio: float = Field(
        ...,
        description=(
            "Multiplier to convert hardware velocity units to rad/s.\n"
            "- Feetech (counts/s): (2π) / 4096\n"
            "- Dynamixel (0.229 RPM units): 0.229 * 2π / 60\n"
            "- Damiao (native rad/s): 1.0"
        ),
    )

    # Additional unit conversion factors (standard units per register unit)
    current_unit_ma_per_bit: float = Field(
        ...,
        description=(
            "Current conversion factor: mA per register unit.\n"
            "- Dynamixel X-series: 2.69 mA/unit\n"
            "- Dynamixel XL330: 3.36 mA/unit\n"
            "- Feetech STS3215: ~6.5 mA/unit\n"
            "- Damiao: 1.0 (current in native units)"
        ),
    )
    voltage_unit_v_per_bit: float = Field(
        ...,
        description=(
            "Voltage conversion factor: volts per register unit.\n"
            "- Dynamixel: 0.1 V/unit\n"
            "- Feetech: 0.1 V/unit\n"
            "- Damiao: 1.0 (voltage in native units)"
        ),
    )
    temperature_unit_c_per_bit: float = Field(
        ...,
        description=(
            "Temperature conversion factor: °C per register unit.\n"
            "- Dynamixel: 1.0 °C/unit (direct mapping)\n"
            "- Feetech: 1.0 °C/unit (direct mapping)\n"
            "- Damiao: 1.0 °C/unit"
        ),
    )
    acceleration_unit_rad_s2_per_bit: float | None = Field(
        None,
        description=(
            "Acceleration conversion factor: rad/s² per register unit.\n"
            "- Dynamixel: 214.577 rev/min² → 0.3738 rad/s² per unit\n"
            "- Others: model-specific"
        ),
    )

    encoding: str | None = None
    endianness: str | None = None
    gear_ratio: float | None = None
    direction_inverted: bool | None = None

    # Protocol references (point to shared objects in protocol tables)
    baudrates: list[int] | None = None

    def get_conversion_factor(self, unit_type: UnitType) -> float:
        """Get the appropriate conversion factor from MotorModelInfo and ensure it exists.

        | Quantity     | Standard Unit              | Symbol |
        |--------------|----------------------------|--------|
        | Position     | radians                    | rad    |
        | Velocity     | radians per second         | rad/s  |
        | Acceleration | radians per second squared | rad/s² |
        | Current      | milliamperes               | mA     |
        | Voltage      | volts                      | V      |
        | Temperature  | degrees Celsius            | °C     |
        | Torque       | Newton-meters              | N·m    |
        | Force        | Newtons                    | N      |
        | Time         | seconds                    | s      |

        Args:
            model_info: Motor model information (must be provided)
            unit_type: Type of physical unit

        Returns:
            Conversion factor (standard_unit per register_unit)

        Raises:
            ValueError: If the requested conversion factor is not defined for the model
        """
        # Map unit types to MotorModelInfo attributes
        if unit_type == "position":
            value = self.position_to_radian_ratio
        elif unit_type == "velocity":
            value = self.velocity_ratio
        elif unit_type == "acceleration":
            value = self.acceleration_unit_rad_s2_per_bit
        elif unit_type == "temperature":
            value = self.temperature_unit_c_per_bit
        elif unit_type == "voltage":
            value = self.voltage_unit_v_per_bit
        elif unit_type == "current":
            value = self.current_unit_ma_per_bit
        elif unit_type == "torque":
            value = 1.0  # Simplified assumption
        else:
            raise ValueError(f"Unknown unit type: {unit_type}")

        if value is None:
            raise ValueError(
                f"No {unit_type} conversion factor defined for motor model "
                f"{self.brand}/{self.model}/{self.variant}"
            )
        return value

    def convert_to_standard_unit(self, unit_type: UnitType, raw_value: float) -> float:
        """Convert a raw register value to standard SI units using the appropriate conversion factor.

        Args:
            unit_type: Type of physical unit
            raw_value: Raw register value from motor

        Returns:
            Converted value in standard SI units

        Raises:
            ValueError: If the requested conversion factor is not defined for the model
        """
        conversion_factor = self.get_conversion_factor(unit_type)
        return raw_value * conversion_factor

    def convert_from_standard_unit(self, unit_type: UnitType, physical_value: float) -> float:
        """Convert a physical value in standard SI units to raw register units using the appropriate conversion factor.

        Args:
            unit_type: Type of physical unit
            physical_value: Value in standard SI units

        Returns:
            Raw register value

        Raises:
            ValueError: If the requested conversion factor is not defined for the model
        """
        conversion_factor = self.get_conversion_factor(unit_type)
        return physical_value / conversion_factor


# `MotorLimitTypes` container removed; use `MotorLimit.LIMIT_*` constants
# or the module-level aliases (e.g., LIMIT_VOLTAGE_MIN) for compatibility.


# ============================================================================
# Robot Definitions (from robots.json)
# ============================================================================


class RobotMotorDefinition(BaseModel):
    """Motor requirement in a robot definition.

    - `name`: logical motor name (joint name) used as dict key in MotorBusDefinition. When loading from
      list-based specs, `name` will be derived from the motor's `id` if not provided.
    - `id`: input alias for the motor id. Internally `id` may be an `int` or a `(send, recv)` tuple.

    Convenience helpers exposed:
      - `motor_id()` -> int: returns the raw id when it is stored as an `int` (raises otherwise)
      - `send_id()` -> int: returns the send id when `id` is a `(send, recv)` tuple (raises otherwise)
      - `recv_id` (int): receive id (equal to `id` when not distinct)
      - `key` (int | tuple): raw key used by drivers and verification (int or (send, recv)).

    - `is_full_turn`: whether this motor has no range limits (full turn capability) and doesn't need calibration
      (default: False). Set to `true` for motors like wheels that rotate freely without position limits.
    """

    name: str | None = None
    id: MotorID = Field(..., description="Raw id (int) or (send, recv) tuple")
    brand: str
    model: str
    variant: str | None = None
    is_full_turn: bool = Field(False, description="Whether the motor has no range limits (full turn, e.g., wheels)")
    drive_mode: int = Field(0, description="0 = normal, 1 = inverted direction")  # default to 0 when missing from JSON
    norm_mode: "MotorNormMode" = Field(
        MotorNormMode.RANGE_M100_100,
        description=(
            "Normalization mode used to compute normalized position values for teleoperation.\n"
            "Missing field in older specs defaults to RANGE_M100_100 (backwards compatible)."
        ),
    )

    @field_validator("id", mode="before")
    def _normalize_id(cls, v: object) -> MotorID | object:
        """Normalize list-style ids into int or tuple forms for `id`.

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

    def motor_id(self) -> int:
        """Return the motor id when `id` is stored as an int. Raises TypeError otherwise."""
        v = object.__getattribute__(self, "id")
        if isinstance(v, int):
            return int(v)
        raise TypeError("motor_id is only available when 'id' is an int")

    def send_id(self) -> int:
        """Return the send id when `id` is a (send, recv) tuple. Raises TypeError otherwise."""
        v = object.__getattribute__(self, "id")
        if isinstance(v, tuple):
            return int(v[0])
        raise TypeError("send_id is only available when 'id' is a tuple (send, recv)")

    @property
    def recv_id(self) -> int:
        """Receive id (int). Equal to `id` when not provided separately."""
        v = object.__getattribute__(self, "id")
        return int(v[1]) if isinstance(v, tuple) else int(v)

    @property
    def key(self) -> MotorID:
        """Return the raw key form used for matching against drivers (int or tuple)."""
        return object.__getattribute__(self, "id")


class MotorBusDefinition(BaseModel):
    """Motor bus definition within a robot.

    `motors` may be provided either as a dict keyed by logical motor name or as a
    list of motor definitions (as historically used in `robots.json`). When a list
    is provided the model will normalize it into a dict keyed by each motor's
    `name` (or by its `id` when `name` is not supplied).
    """

    type: str
    motors: dict[str, RobotMotorDefinition]
    baud_rate: int | None = None  # Serial baud rate or CAN bitrate
    interface_type: str | None = None  # serial, can, slcan, etc.


class RobotDefinition(BaseModel):
    """Robot configuration definition from robots.json."""

    id: str
    lerobot_name: str | None = None
    display_name: str | dict[str, str]
    description: str | dict[str, str]
    image: str | None = None
    support_version_from: str | None = None
    support_version_end: str | None = None
    device_category: DeviceCategory = Field(DeviceCategory.ROBOT, description="Device category (robot|controller)")
    motor_buses: dict[str, MotorBusDefinition]

    class Config:
        use_enum_values = True


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

# ============================================================================
# Teleoperation Protocol Models (WebSocket Commands & Responses)
# ============================================================================


class SetPositionsCommand(BaseModel):
    """Command to set motor positions.

    Structure: dict[bus_name] -> dict[motor_name] -> position value
    Motor names are logical names from robot definition.
    Service layer converts names to MotorIDs for motor bus operations.
    """

    type: Literal["set_positions"] = "set_positions"
    motor_positions: dict[str, dict[str, float]] = Field(
        ..., description="Mapping from bus_name to {motor_name: position}"
    )


class SetTorquesCommand(BaseModel):
    """Command to enable/disable motor torques.

    Structure: dict[bus_name] -> dict[motor_name] -> enabled state
    Motor names are logical names from robot definition.
    """

    type: Literal["set_torques"] = "set_torques"
    motor_enabled: dict[str, dict[str, bool]] = Field(..., description="Mapping from bus_name to {motor_name: enabled}")


class SetVelocitiesCommand(BaseModel):
    """Command to set motor velocities.

    Structure: dict[bus_name] -> dict[motor_name] -> velocity value
    Motor names are logical names from robot definition.
    """

    type: Literal["set_velocities"] = "set_velocities"
    motor_velocities: dict[str, dict[str, float]] = Field(
        ..., description="Mapping from bus_name to {motor_name: velocity}"
    )


class EmergencyStopCommand(BaseModel):
    """Command to emergency stop all motors (disable torque)."""

    type: Literal["emergency_stop"] = "emergency_stop"


class PollingCommand(BaseModel):
    """Command to pause/resume motor data polling."""

    type: Literal["polling"] = "polling"
    enabled: bool = Field(..., description="Enable or disable polling")


class SetHomingOffsetsCommand(BaseModel):
    """Command to set homing offsets for motors.

    Homing offsets are calculated based on current motor positions
    and range data provided by the frontend.

    Structure: dict[bus_name] -> dict[motor_name] -> {range_min, range_max}
    Motor names are logical names from robot definition.
    """

    type: Literal["set_homing_offsets"] = "set_homing_offsets"
    motor_offsets: dict[str, dict[str, dict[str, int]]] = Field(
        ..., description="Mapping from bus_name to motor_name to {range_min, range_max}"
    )


class SetRangesCommand(BaseModel):
    """Command to set position ranges for motors.

    Range limits define the valid range of motion for each motor in raw encoder units.

    Structure: dict[bus_name] -> dict[motor_name] -> {range_min, range_max}
    Motor names are logical names from robot definition.
    """

    type: Literal["set_ranges"] = "set_ranges"
    motor_ranges: dict[str, dict[str, dict[str, int]]] = Field(
        ..., description="Mapping from bus_name to motor_name to {range_min, range_max}"
    )


class HeartbeatCommand(BaseModel):
    """Heartbeat message to keep the connection alive.

    Client sends periodically to indicate the connection is still active.
    Server uses this to detect inactive connections.
    """

    type: Literal["heartbeat"] = "heartbeat"


class WebSocketCommand(
    RootModel[
        SetPositionsCommand
        | SetTorquesCommand
        | SetVelocitiesCommand
        | EmergencyStopCommand
        | PollingCommand
        | SetHomingOffsetsCommand
        | SetRangesCommand
        | HeartbeatCommand
    ]
):
    """Union of all possible WebSocket commands from client.

    Pydantic v2 uses RootModel for discriminated unions where the discriminator
    is embedded in the union types themselves (via the 'type' field).
    """

    pass


class TelemetryMessage(BaseModel):
    """Telemetry message sent to client."""

    type: Literal["telemetry"] = "telemetry"
    frame: RobotTelemetryFrame


class CommandAckMessage(BaseModel):
    """Acknowledgment for a successful command."""

    type: Literal["command_ack"] = "command_ack"
    command_type: str = Field(..., description="Type of command that was executed")
    success: bool = Field(True, description="Whether the command succeeded")
    message: str | None = Field(None, description="Optional status message")


class ErrorMessage(BaseModel):
    """Error message sent to client."""

    type: Literal["error"] = "error"
    code: str = Field(..., description="Error code (e.g., 'DEVICE_NOT_AVAILABLE', 'COMMAND_FAILED')")
    message: str = Field(..., description="Human-readable error message")
    details: dict[str, Any] = Field(default_factory=dict, description="Additional error details")


class SessionInitMessage(BaseModel):
    """Session initialization message sent when connection is established."""

    type: Literal["session_init"] = "session_init"
    robot_id: str = Field(..., description="Robot ID")
    normalized: bool = Field(..., description="Whether telemetry is normalized")
    fps: int = Field(..., description="Configured frames per second")


class WebSocketMessage(RootModel[SessionInitMessage | TelemetryMessage | CommandAckMessage | ErrorMessage]):
    """Union of all possible WebSocket messages from server.

    Pydantic v2 uses RootModel for discriminated unions where the discriminator
    is embedded in the union types themselves (via the 'type' field).
    """

    pass
