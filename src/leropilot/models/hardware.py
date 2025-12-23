"""Hardware related models."""

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class HardwareCapabilities(BaseModel):
    """System hardware capabilities."""

    has_nvidia_gpu: bool = False
    has_amd_gpu: bool = False
    is_apple_silicon: bool = False
    detected_cuda: str | None = None
    detected_rocm: str | None = None


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


class Device(BaseModel):
    """Base device model stored in list.json."""

    id: str = Field(..., description="Unique serial number from hardware")
    category: DeviceCategory
    name: str = Field(..., description="User-friendly device name")
    status: DeviceStatus = Field(DeviceStatus.AVAILABLE, description="Runtime device status")
    manufacturer: str | None = Field(None, description="Manufacturer from discovery (read-only)")
    # model: Deprecated/Removed. Use labels['leropilot.ai/robot_type_id']
    labels: dict[str, str] = Field(default_factory=dict, description="Key-value labels for automation")
    created_at: datetime = Field(default_factory=datetime.now)
    # connection_settings: connection info only (brand, interface, etc.)
    connection_settings: dict[str, Any] = Field(default_factory=dict, description="Connection parameters")
    # config: detailed configuration (calibration, protection) - merged at runtime
    config: Optional["DeviceConfig"] = Field(None, description="Detailed configuration (merged details)")

    class Config:
        use_enum_values = True


class MotorInfo(BaseModel):
    """Motor identification information from bus scan."""

    id: int = Field(..., description="Motor ID on the bus (1-254)")
    model: str = Field(..., description="Base model name (e.g., XL430, STS3215)")
    variant: str | None = Field(None, description="Specific variant or spec (e.g., W250, C001)")
    model_number: int = Field(..., description="Numeric model identifier")
    firmware_version: str | None = Field(None, description="Firmware version string")

    @property
    def full_name(self) -> str:
        """Return combined model and variant name."""
        if self.variant:
            return f"{self.model}-{self.variant}"
        return self.model


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
    """Motor calibration data (compatible with lerobot format)."""

    id: int = Field(..., description="Motor ID on the bus")
    drive_mode: int = Field(0, description="0 = normal, 1 = inverted direction")
    homing_offset: int = Field(..., description="Encoder offset for zero position (raw units)")
    range_min: int = Field(..., description="Minimum position limit (raw encoder units)")
    range_max: int = Field(..., description="Maximum position limit (raw encoder units)")


class MotorProtectionParams(BaseModel):
    """Motor protection parameters."""

    model_ids: list[int] = Field(default_factory=list, description="Possible model IDs for detection")
    temp_warning: int = Field(..., description="Warning temperature threshold (°C)")
    temp_critical: int = Field(..., description="Critical temperature threshold (°C)")
    temp_max: int = Field(..., description="Absolute max temperature from datasheet (°C)")
    voltage_min: float = Field(..., description="Minimum safe voltage (V)")
    voltage_max: float = Field(..., description="Maximum safe voltage (V)")
    current_max: int = Field(..., description="Maximum continuous current (mA)")
    current_peak: int = Field(..., description="Peak current limit (mA)")
    datasheet_url: str | None = Field(None, description="Link to motor datasheet")


# ============================================================================
# Motor Protection Database
# ============================================================================


class MotorSpecification(BaseModel):
    """Built-in motor specifications (from motor_specs.json)"""

    brand: MotorBrand
    model: str
    model_ids: list[int] = Field(..., description="Possible model IDs for detection")
    description: str | None = None
    temp_warning: int
    temp_critical: int
    temp_max: int
    voltage_min: float
    voltage_max: float
    current_max: int
    current_peak: int
    datasheet_url: str | None = None


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


class DeviceConfig(BaseModel):
    """Detailed device configuration (stored in config.json)"""

    motors: dict[str, MotorConfig] = Field(default_factory=dict, description="Per-motor configuration")
    custom: dict[str, Any] = Field(default_factory=dict, description="User custom settings")


# ============================================================================
# Robot Definitions (from robots.json)
# ============================================================================


class RobotMotorDefinition(BaseModel):
    """Motor requirement in a robot definition."""

    id: int
    brand: str
    model: str
    variant: str | None = None


class RobotDefinition(BaseModel):
    """Robot configuration definition from robots.json."""

    id: str
    lerobot_name: str | None = None
    display_name: str
    description: str
    support_version_from: str | None = None
    support_version_end: str | None = None
    motors: list[RobotMotorDefinition]


# ============================================================================
# Discovery Results
# ============================================================================


class DiscoveredDevice(BaseModel):
    """Generic discovered device"""

    port: str | None = None  # For serial devices
    channel: str | None = None  # For CAN devices
    vid: str = Field(..., description="USB Vendor ID")
    pid: str = Field(..., description="USB Product ID")
    manufacturer: str
    description: str
    serial_number: str | None = None
    status: DeviceStatus
    supported: bool = True
    unsupported_reason: str | None = None


class DiscoveredRobot(DiscoveredDevice):
    """Discovered robot/arm device"""

    pass


class DiscoveredController(DiscoveredDevice):
    """Discovered controller device"""

    pass


class DiscoveryResult(BaseModel):
    """Complete hardware discovery result"""

    robots: list[DiscoveredRobot] = []
    controllers: list[DiscoveredController] = []


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
    discovered_motors: list[MotorInfo] = []
    suggested_robots: list[SuggestedRobot] = []
    logs: list[str] = []


# ============================================================================
# Motor Scan Results
# ============================================================================


class MotorScanResult(BaseModel):
    """Result from motor bus scan"""

    motors: list[MotorInfo]
    suggested_robots: list[SuggestedRobot] | None = None
    scan_duration_ms: float


# ============================================================================
# Device Settings & Configuration
# ============================================================================


class ConnectionSettings(BaseModel):
    """Motor bus connection settings"""

    interface_type: InterfaceType = InterfaceType.SERIAL
    baud_rate: int | None = None  # Serial baud or CAN bit rate
    brand: MotorBrand = MotorBrand.DYNAMIXEL


class DeviceConnectionSettings(BaseModel):
    """Device connection settings (stored in list.json)"""

    interface_type: InterfaceType = InterfaceType.SERIAL
    baud_rate: int | None = None  # Serial baud or CAN bit rate
    brand: MotorBrand = MotorBrand.DYNAMIXEL


# ============================================================================
# All Motors Telemetry
# ============================================================================


class AllMotorsTelemetry(BaseModel):
    """All motors telemetry snapshot"""

    motors: list[MotorTelemetry]
    timestamp: datetime = Field(default_factory=datetime.now)
    hardware_timestamp: datetime | None = None
