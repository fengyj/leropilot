"""Damiao motor model tables and protocol constants.

Express Damiao models as typed `MotorModelInfo` entries to support
MotorService table-based lookups and to retire `motor_specs.json`.
"""

from __future__ import annotations

from leropilot.models.hardware import MotorBrand, MotorModelInfo


class DamiaoConstants:
    """CAN protocol constants and addresses for Damiao motors."""

    # CAN command constants
    CMD_ENABLE = 0xFC
    CMD_DISABLE = 0xFD
    CMD_SET_ZERO = 0xFE
    CMD_REFRESH = 0xCC  # Fixed: was 0xF5, should be 0xCC per openarm_can/lerobot reference implementations

    # Parameter access commands (from lerobot reference)
    CAN_CMD_QUERY_PARAM = 0x33
    CAN_CMD_WRITE_PARAM = 0x55
    CAN_CMD_SAVE_PARAM = 0xAA

    # CAN parameter ID for parameter access
    PARAM_ID = 0x7FF

    # Default CAN settings
    DEFAULT_BAUDRATE = 1000000  # 1 Mbps
    AVAILABLE_BAUDRATES = [1000000, 2000000, 5000000]  # CAN FD supported
    DEFAULT_TIMEOUT_MS = 1000

    # Motor type specific limits for MIT control (pmax, vmax, tmax)
    # Values from lerobot reference implementation
    MOTOR_LIMIT_PARAMS = {
        "DM4310": (12.5, 30.0, 10.0),  # Position (rad), Velocity (rad/s), Torque (N·m)
        "DM4340": (12.5, 8.0, 28.0),  # Lower velocity, higher torque
        "DM4340P": (12.5, 10.0, 28.0),  # P variant with cross-roller bearings
        "DM8009": (12.5, 45.0, 54.0),  # High torque shoulder motor
        "DM8009P": (12.5, 45.0, 54.0),  # P variant with cross-roller bearings
        "DM6006": (12.5, 45.0, 20.0),
        "DM8006": (12.5, 45.0, 40.0),
        "DM10054": (12.5, 45.0, 18.0),
    }


# Common feature set for Damiao models (used to avoid future duplication)
DAMIAO_DEFAULT_FEATURES = frozenset({"position", "velocity", "voltage", "temperature", "current", "goal_position"})

DAMAIO_MODELS_LIST: list[MotorModelInfo] = [
    MotorModelInfo(
        model="DM",
        model_ids=[],
        limits={},
        variant=None,
        description="Damiao servo motor",
        encoder_resolution=65536.0,
        position_to_radian_ratio=1.0,
        velocity_ratio=1.0,
        current_unit_ma_per_bit=1000.0,
        voltage_unit_v_per_bit=1.0,
        temperature_unit_c_per_bit=1.0,
        acceleration_unit_rad_s2_per_bit=None,
        brand=MotorBrand.DAMIAO,
    ),
]


def models_for_id(model_id: int) -> list[MotorModelInfo]:
    return [m for m in DAMAIO_MODELS_LIST if int(model_id) in (m.model_ids or [])]


# Register models for global lookup
try:
    from ..base import MotorUtil

    MotorUtil.register_models(DAMAIO_MODELS_LIST)
except Exception:
    pass


def select_model_for_number(
    model_number: int,
    fw_major: int | None = None,
    fw_minor: int | None = None,
) -> MotorModelInfo | None:
    candidates = models_for_id(model_number)
    if not candidates:
        return None
    if len(candidates) == 1:
        return candidates[0]
    # prefer base
    for c in candidates:
        if c.variant is None:
            return c
    return candidates[0]


class DamiaoRegisters:
    """Common parameter addresses for Damiao motors.

    Each register is expressed as a (address, length_in_bytes) tuple and is
    intended to be used with Damiao parameter access commands (see
    :pyattr:`DamiaoConstants.PARAM_ID`). Values are taken from the
    "DM-J4310-2EC V1.2" draft manual (linked in project issues); verify
    against your specific motor firmware before writing EEPROM-critical
    locations.

    Source: https://github.com/dmBots/DM-J4310-2EC/blob/a3705a7124.../DM-J4310-2EC%20V1.2%E5%87%8F%E9%80%9F%E7%94%B5%E6%9C%BA%E8%AF%B4%E6%98%8E%E4%B9%A6%20%E5%88%9D%E7%A8%BF%E6%9C%80%E6%96%B0.pdf
    """

    # Identification / protection (access: RW/RO)
    # Format: (address, is_rw (True if RW), is_float)
    UV_VALUE = (0x00, True, True)  # under-voltage protection value (float)
    KT_VALUE = (0x01, True, True)  # torque constant (float)

    # Note: there is no stable 'model number' register in the official DM-J4310
    # documentation. Address 0x01 is the KT_VALUE parameter (torque constant) and
    # should not be treated as a model identifier. Older community code sometimes
    # returned identifying values at 0x00 or 0x100 on particular firmwares; those
    # addresses are *heuristics* only and are handled in driver logic as a fallback.
    # (Do not introduce a MODEL_NUMBER alias that would imply a documented register.)
    # MODEL_NUMBER aliases intentionally omitted to avoid confusion.

    OT_VALUE = (0x02, True, True)  # over-temperature protection value (float)
    OC_VALUE = (0x03, True, True)  # over-current protection value (float)

    # Motion configuration
    ACC = (0x04, True, True)  # acceleration (float)
    DEC = (0x05, True, True)  # deceleration (float)
    MAX_SPD = (0x06, True, True)  # maximum speed (float)

    # CAN / IDs / timeouts
    MST_ID = (0x07, True, False)  # master id (uint32)
    ESC_ID = (0x08, True, False)  # receiver id (uint32)
    TIMEOUT = (0x09, True, False)  # timeout (uint32)

    # Control mode (stored as uint32 in registers; values range small, e.g., 0-4)
    CTRL_MODE = (0x0A, True, False)  # control mode (uint32)

    # Read-only mechanical / hardware info
    DAMP = (0x0B, False, True)
    INERTIA = (0x0C, False, True)
    HW_VER = (0x0D, False, False)
    SW_VER = (0x0E, False, False)
    SN = (0x0F, False, False)

    # Motor params
    NPP = (0x10, False, False)
    Rs = (0x11, False, True)
    Ls = (0x12, False, True)
    Flux = (0x13, False, True)
    Gr = (0x14, False, True)

    # Mapping / limits (position/velocity/torque mapping ranges)
    PMAX = (0x15, True, True)  # position mapping max (float)
    VMAX = (0x16, True, True)  # velocity mapping max (float)
    TMAX = (0x17, True, True)  # torque mapping max (float)

    # Current control / PID (speed & position loops)
    I_BW = (0x18, True, True)
    KP_ASR = (0x19, True, True)  # speed loop Kp
    KI_ASR = (0x1A, True, True)  # speed loop Ki
    KP_APR = (0x1B, True, True)  # position loop Kp
    KI_APR = (0x1C, True, True)  # position loop Ki

    OV_VALUE = (0x1D, True, True)
    GREF = (0x1E, True, True)
    DETA = (0x1F, True, True)

    # Additional control params
    V_BW = (0x20, True, True)
    IQ_C1 = (0x21, True, True)
    VL_C1 = (0x22, True, True)
    CAN_BR = (0x23, True, False)  # CAN baudrate code

    # Sub/boot versions
    SUB_VER = (0x24, False, False)
    BOOT_VER = (0x25, False, False)

    # Misc / diagnostics
    DIR = (0x37, False, True)
    M_OFF = (0x38, False, True)
    IMAX = (0x3B, False, True)
    VBUS = (0x3C, False, True)
    TPCB = (0x3D, False, True)
    TMTR = (0x3E, False, True)
    IU_OFF = (0x3F, False, True)
    IV_OFF = (0x40, False, True)
    IW_OFF = (0x41, False, True)

    # Live position outputs
    P_M = (0x50, False, True)  # motor current position (rad)
    XOUT = (0x51, False, True)  # output shaft position (rad)

    @classmethod
    def get_register_info(cls, address: int) -> tuple[int, bool, bool]:
        """Return (addr, is_rw, is_float) for the given register address.

        This method accepts both the new 3-tuple format and the legacy 2-tuple
        format for backward compatibility.
        """
        for name in dir(cls):
            if not name.isupper():
                continue
            val = getattr(cls, name)
            if not isinstance(val, tuple) or len(val) == 0:
                continue
            try:
                addr = int(val[0])
            except Exception:
                continue
            if addr != address:
                continue
            if len(val) >= 3:
                # New format: (addr, is_rw, is_float)
                return (addr, bool(val[1]), bool(val[2]))
            # Legacy format: (addr, is_read_only)
            is_read_only = bool(val[1]) if len(val) >= 2 else False
            is_rw = not is_read_only
            # Best-effort default: assume float for legacy entries unless name contains 'ID' or 'VER' or 'SN' etc.
            name_lower = name.lower()
            is_float = not any(k in name_lower for k in ("id", "ver", "sn", "boot", "can_br", "timeout"))
            return (addr, is_rw, is_float)
        raise ValueError(f"Unknown Damiao register address: 0x{address:02X}")


# Per-model supported parameter/register sets
# Each tuple: (set of model base names), set of supported register addresses (int)
DAMAIO_REGISTER_SUPPORT: list[tuple[set[str], set[int]]] = [
    (
        {"dm4310", "dm4340", "dm4340p", "dm6006", "dm8006", "dm8009", "dm8009p", "dm10054"},
        {
            # Identification
            0x00,  # UV_VALUE / alt model read
            0x01,  # KT_VALUE / model number in some firmwares
            0x100,  # fallback model number
            # Motion / control
            DamiaoRegisters.ACC[0],
            DamiaoRegisters.DEC[0],
            DamiaoRegisters.MAX_SPD[0],
            DamiaoRegisters.CTRL_MODE[0],
            # Mapping / limits
            DamiaoRegisters.PMAX[0],
            DamiaoRegisters.VMAX[0],
            DamiaoRegisters.TMAX[0],
            # PID gains
            DamiaoRegisters.KP_ASR[0],
            DamiaoRegisters.KI_ASR[0],
            DamiaoRegisters.KP_APR[0],
            DamiaoRegisters.KI_APR[0],
            # Diagnostics / outputs
            DamiaoRegisters.P_M[0],
            DamiaoRegisters.XOUT[0],
        },
    ),
]


def damiao_supports_register(model_name: str, register_addr: int) -> bool:
    """Return True if the given Damiao `register_addr` is supported for `model_name`.

    Matching is case-insensitive against known base model names. Unknown models
    return False.
    """
    m = model_name.lower()
    for models_set, addrs in DAMAIO_REGISTER_SUPPORT:
        if m in models_set:
            return register_addr in addrs
    return False
