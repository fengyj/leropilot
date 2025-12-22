"""Hardware related models."""

from pydantic import BaseModel


class HardwareCapabilities(BaseModel):
    """System hardware capabilities."""

    has_nvidia_gpu: bool = False
    has_amd_gpu: bool = False
    is_apple_silicon: bool = False
    detected_cuda: str | None = None
    detected_rocm: str | None = None


# Hardware Device Management Models

from enum import Enum
from typing import Optional, Dict, List, Any
from pydantic import Field
from datetime import datetime


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
    manufacturer: Optional[str] = Field(None, description="Manufacturer from discovery (read-only)")
    # model: Deprecated/Removed. Use labels['leropilot.ai/robot_type_id']
    labels: Dict[str, str] = Field(default_factory=dict, description="Key-value labels for automation")
    created_at: datetime = Field(default_factory=datetime.now)
    # connection_settings: connection info only (brand, interface, etc.)
    connection_settings: Dict[str, Any] = Field(default_factory=dict, description="Connection parameters")
    # config: detailed configuration (calibration, protection) - merged at runtime
    config: Optional["DeviceConfig"] = Field(None, description="Detailed configuration (merged details)")

    class Config:
        use_enum_values = True


class MotorInfo(BaseModel):
    """Motor identification information from bus scan."""
    id: int = Field(..., description="Motor ID on the bus (1-254)")
    model: str = Field(..., description="Base model name (e.g., XL430, STS3215)")
    variant: Optional[str] = Field(None, description="Specific variant or spec (e.g., W250, C001)")
    model_number: int = Field(..., description="Numeric model identifier")
    firmware_version: Optional[str] = Field(None, description="Firmware version string")

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
    violations: List[ProtectionViolation] = Field(default_factory=list)


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
    model_ids: List[int] = Field(default_factory=list, description="Possible model IDs for detection")
    temp_warning: int = Field(..., description="Warning temperature threshold (°C)")
    temp_critical: int = Field(..., description="Critical temperature threshold (°C)")
    temp_max: int = Field(..., description="Absolute max temperature from datasheet (°C)")
    voltage_min: float = Field(..., description="Minimum safe voltage (V)")
    voltage_max: float = Field(..., description="Maximum safe voltage (V)")
    current_max: int = Field(..., description="Maximum continuous current (mA)")
    current_peak: int = Field(..., description="Peak current limit (mA)")
    datasheet_url: Optional[str] = Field(None, description="Link to motor datasheet")


# ============================================================================
# Motor Protection Database
# ============================================================================

class MotorSpecification(BaseModel):
    """Built-in motor specifications (from motor_specs.json)"""
    brand: MotorBrand
    model: str
    model_ids: List[int] = Field(..., description="Possible model IDs for detection")
    description: Optional[str] = None
    temp_warning: int
    temp_critical: int
    temp_max: int
    voltage_min: float
    voltage_max: float
    current_max: int
    current_peak: int
    datasheet_url: Optional[str] = None


class MotorProtectionOverride(BaseModel):
    """User custom motor protection overrides"""
    source: str = Field("builtin", description="'builtin' or 'custom'")
    overrides: Optional[Dict[str, float]] = None  # e.g., {"temp_warning": 55}


class DeviceProtection(BaseModel):
    """Protection configuration for a device"""
    temp_limit: int = 60
    voltage_min: float = 10.0
    overrides: Dict[str, float] = Field(default_factory=dict)
    # We can also store per-motor overrides if needed
    
class MotorConfig(BaseModel):
    """Configuration for a single motor."""
    calibration: Optional[MotorCalibration] = None
    protection: Optional[MotorProtectionOverride] = None

class DeviceConfig(BaseModel):
    """Detailed device configuration (stored in config.json)"""
    motors: Dict[str, MotorConfig] = Field(default_factory=dict, description="Per-motor configuration")
    custom: Dict[str, Any] = Field(default_factory=dict, description="User custom settings")


# ============================================================================
# Robot Definitions (from robots.json)
# ============================================================================

class RobotMotorDefinition(BaseModel):
    """Motor requirement in a robot definition."""
    id: int
    brand: str
    model: str
    variant: Optional[str] = None


class RobotDefinition(BaseModel):
    """Robot configuration definition from robots.json."""
    id: str
    lerobot_name: Optional[str] = None
    display_name: str
    description: str
    support_version_from: Optional[str] = None
    support_version_end: Optional[str] = None
    motors: List[RobotMotorDefinition]


# ============================================================================
# Discovery Results
# ============================================================================

class DiscoveredDevice(BaseModel):
    """Generic discovered device"""
    port: Optional[str] = None  # For serial devices
    channel: Optional[str] = None  # For CAN devices
    vid: str = Field(..., description="USB Vendor ID")
    pid: str = Field(..., description="USB Product ID")
    manufacturer: str
    description: str
    serial_number: Optional[str] = None
    status: DeviceStatus
    supported: bool = True
    unsupported_reason: Optional[str] = None


class DiscoveredRobot(DiscoveredDevice):
    """Discovered robot/arm device"""
    pass


class DiscoveredController(DiscoveredDevice):
    """Discovered controller device"""
    pass


class DiscoveredCamera(BaseModel):
    """Discovered camera device"""
    index: int = Field(..., description="Camera index (0, 1, ...)")
    instance_id: str = Field(..., description="Unique instance identifier")
    name: str = Field(..., description="Camera name")
    friendly_name: str
    type: str = Field(..., description="Camera type (USB, RealSense, etc.)")
    vid: str
    pid: str
    serial_number: Optional[str] = None
    manufacturer: str
    width: Optional[int] = None
    height: Optional[int] = None
    status: DeviceStatus
    supported: bool = True
    unsupported_reason: Optional[str] = None


class DiscoveryResult(BaseModel):
    """Complete hardware discovery result"""
    robots: List[DiscoveredRobot] = []
    controllers: List[DiscoveredController] = []
    cameras: List[DiscoveredCamera] = []


# ============================================================================
# Probe Connection Results
# ============================================================================

class SuggestedRobot(BaseModel):
    """Suggested robot configuration from robots.json match."""
    id: str
    lerobot_name: str
    display_name: str


class ProbeConnectionResult(BaseModel):
    """Result from probe-connection endpoint"""
    interface: str
    interface_type: InterfaceType
    brand: MotorBrand
    baud_rate: int
    discovered_motors: List[MotorInfo] = []
    suggested_robots: List[SuggestedRobot] = []
    logs: List[str] = []


# ============================================================================
# Motor Scan Results
# ============================================================================

class MotorScanResult(BaseModel):
    """Result from motor bus scan"""
    motors: List[MotorInfo]
    suggested_robots: Optional[List[SuggestedRobot]] = None
    scan_duration_ms: float


# ============================================================================
# Device Settings & Configuration
# ============================================================================

class ConnectionSettings(BaseModel):
    """Motor bus connection settings"""
    interface_type: InterfaceType = InterfaceType.SERIAL
    baud_rate: Optional[int] = None  # Serial baud or CAN bit rate
    brand: MotorBrand = MotorBrand.DYNAMIXEL


class DeviceConnectionSettings(BaseModel):
    """Device connection settings (stored in list.json)"""
    interface_type: InterfaceType = InterfaceType.SERIAL
    baud_rate: Optional[int] = None  # Serial baud or CAN bit rate
    brand: MotorBrand = MotorBrand.DYNAMIXEL


# ============================================================================
# All Motors Telemetry
# ============================================================================

class AllMotorsTelemetry(BaseModel):
    """All motors telemetry snapshot"""
    motors: List[MotorTelemetry]
    timestamp: datetime = Field(default_factory=datetime.now)
    hardware_timestamp: Optional[datetime] = None

