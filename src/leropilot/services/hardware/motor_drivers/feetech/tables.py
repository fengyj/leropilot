"""Feetech series register definitions and model tables (drivers subpackage).

This file centralizes Feetech-specific constants (per-series registers) and
MotorModelInfo entries for the Feetech family. Model definitions include
`model_ids` and `limits` so they are self-contained and do not rely on
`motor_specs.json` at runtime. The legacy compatibility shim under
`services.hardware.feetech_tables` imports this module.
"""

from __future__ import annotations

import math

from leropilot.models.hardware import MotorBrand, MotorLimit, MotorModelInfo


class SCS_STS_Registers:
    """Registers for the STS/SCS series (uses SCS style addressing).

    Each register is a tuple of (address, length_in_bytes).
    """

    FIRMWARE_MAJOR = (0, 1)
    FIRMWARE_MINOR = (1, 1)
    MODEL_NUMBER = (3, 2)
    ID = (5, 1)
    BAUD_RATE = (6, 1)
    TORQUE_ENABLE = (40, 1)
    GOAL_POSITION = (42, 2)
    GOAL_VELOCITY = (46, 2)
    PRESENT_POSITION = (56, 2)
    PRESENT_VELOCITY = (58, 2)
    PRESENT_LOAD = (60, 2)
    PRESENT_VOLTAGE = (62, 1)
    PRESENT_TEMPERATURE = (63, 1)
    PRESENT_CURRENT = (69, 2)

    # Configuration registers
    OPERATING_MODE = (33, 1)
    CURRENT_LIMIT = (22, 2)  # Maximum current
    VELOCITY_LIMIT = (46, 2)  # Same as GOAL_VELOCITY register
    TEMPERATURE_LIMIT = (18, 1)
    MAX_POSITION_LIMIT = (11, 2)  # Same as RANGE_MAX
    MIN_POSITION_LIMIT = (9, 2)  # Same as RANGE_MIN

    # Homing/range register addresses (from lerobot Feetech control table):
    HOMING_OFFSET = (31, 2)
    RANGE_MIN = (9, 2)
    RANGE_MAX = (11, 2)


class FeetechUnits:
    """Unit conversion factors for Feetech SCS/STS motors.

    Based on STS3215/SCS0009/SCS215 specifications.
    Different models may have different conversion factors.
    """

    # Current: Varies by model
    # STS3215: ~6.5mA per unit (1000mA / 150 units from spec)
    # This is an approximation; check motor manual for exact value
    CURRENT_MA_PER_UNIT = 6.5

    # Velocity: For STS3215 with 4096 encoder
    # 1 unit = 1 step/s, convert to rad/s: (2π / 4096) rad/s
    VELOCITY_RAD_S_PER_UNIT = (2 * math.pi) / 4096

    # Temperature: 1°C per unit (direct mapping)
    TEMPERATURE_C_PER_UNIT = 1.0

    # Voltage: 0.1V per unit
    VOLTAGE_V_PER_UNIT = 0.1


# Signed register encoding table for sign-magnitude conversion
# Maps register address to sign bit position
# Feetech motors use sign-magnitude encoding (not two's complement)
# For 16-bit values: sign bit is at position 15
# For 12-bit values: sign bit is at position 11
SIGNED_REGISTERS: dict[int, int] = {
    SCS_STS_Registers.PRESENT_VELOCITY[0]: 15,  # 16-bit sign-magnitude
    SCS_STS_Registers.PRESENT_LOAD[0]: 15,  # 16-bit sign-magnitude
    SCS_STS_Registers.PRESENT_CURRENT[0]: 15,  # 16-bit sign-magnitude
    SCS_STS_Registers.HOMING_OFFSET[0]: 11,  # 12-bit sign-magnitude
    SCS_STS_Registers.GOAL_VELOCITY[0]: 15,  # 16-bit sign-magnitude
}


# Model definitions for Feetech motors (STS/SCS families).
# Each entry is a separate MotorModelInfo with model_ids and limits populated.


SCS_STS_MODELS_LIST: list[MotorModelInfo] = [
    # Base model (variant None) - useful when model_id alone doesn't determine variant
    MotorModelInfo(
        model="STS3215",
        model_ids=[3215, 1545, 0x0C8F],
        limits={
            MotorLimit.LIMIT_VOLTAGE_MIN: MotorLimit(type=MotorLimit.LIMIT_VOLTAGE_MIN, value=6.0),
            MotorLimit.LIMIT_VOLTAGE_MAX: MotorLimit(type=MotorLimit.LIMIT_VOLTAGE_MAX, value=7.4),
            MotorLimit.LIMIT_CURRENT_MAX_MA: MotorLimit(type=MotorLimit.LIMIT_CURRENT_MAX_MA, value=150.0),
            MotorLimit.LIMIT_TEMPERATURE_MAX_C: MotorLimit(type=MotorLimit.LIMIT_TEMPERATURE_MAX_C, value=70.0),
        },
        variant=None,
        description="Feetech STS3215 base model (variant unknown)",
        encoder_resolution=4096.0,
        position_to_radian_ratio=(2 * math.pi) / 4096,
        velocity_ratio=(2 * math.pi) / 4096,
        current_unit_ma_per_bit=6.5,
        voltage_unit_v_per_bit=0.1,
        temperature_unit_c_per_bit=1.0,
        acceleration_unit_rad_s2_per_bit=None,
        gear_ratio=1.0,
        brand=MotorBrand.FEETECH,
    ),
    # Specific variants
    MotorModelInfo(
        model="STS3215",
        model_ids=[49153],
        limits={
            MotorLimit.LIMIT_VOLTAGE_MIN: MotorLimit(type=MotorLimit.LIMIT_VOLTAGE_MIN, value=6.0),
            MotorLimit.LIMIT_VOLTAGE_MAX: MotorLimit(type=MotorLimit.LIMIT_VOLTAGE_MAX, value=7.4),
            MotorLimit.LIMIT_CURRENT_MAX_MA: MotorLimit(type=MotorLimit.LIMIT_CURRENT_MAX_MA, value=150.0),
            MotorLimit.LIMIT_TEMPERATURE_MAX_C: MotorLimit(type=MotorLimit.LIMIT_TEMPERATURE_MAX_C, value=70.0),
        },
        variant="STS3215-C001",
        description="STS3215 SO-101 variant C001",
        encoder_resolution=4096.0,
        position_to_radian_ratio=(2 * math.pi) / 4096,
        velocity_ratio=(2 * math.pi) / 4096,
        current_unit_ma_per_bit=6.5,
        voltage_unit_v_per_bit=0.1,
        temperature_unit_c_per_bit=1.0,
        acceleration_unit_rad_s2_per_bit=None,
        gear_ratio=1.0,
        brand=MotorBrand.FEETECH,
    ),
    MotorModelInfo(
        model="STS3215",
        model_ids=[49220, 49222],
        limits={
            MotorLimit.LIMIT_VOLTAGE_MIN: MotorLimit(type=MotorLimit.LIMIT_VOLTAGE_MIN, value=4.0),
            MotorLimit.LIMIT_VOLTAGE_MAX: MotorLimit(type=MotorLimit.LIMIT_VOLTAGE_MAX, value=14.0),
            MotorLimit.LIMIT_CURRENT_MAX_MA: MotorLimit(type=MotorLimit.LIMIT_CURRENT_MAX_MA, value=180.0),
            MotorLimit.LIMIT_TEMPERATURE_MAX_C: MotorLimit(type=MotorLimit.LIMIT_TEMPERATURE_MAX_C, value=60.0),
        },
        variant="STS3215-C018",
        description="STS3215 high performance C018",
        encoder_resolution=4096.0,
        position_to_radian_ratio=(2 * math.pi) / 4096,
        velocity_ratio=(2 * math.pi) / 4096,
        current_unit_ma_per_bit=6.5,
        voltage_unit_v_per_bit=0.1,
        temperature_unit_c_per_bit=1.0,
        acceleration_unit_rad_s2_per_bit=None,
        gear_ratio=1.0,
        brand=MotorBrand.FEETECH,
    ),
    MotorModelInfo(
        model="STS3215",
        model_ids=[3215, 1545, 0x0C8F],  # Same as base model
        limits={
            MotorLimit.LIMIT_VOLTAGE_MIN: MotorLimit(type=MotorLimit.LIMIT_VOLTAGE_MIN, value=6.0),
            MotorLimit.LIMIT_VOLTAGE_MAX: MotorLimit(type=MotorLimit.LIMIT_VOLTAGE_MAX, value=7.4),
            MotorLimit.LIMIT_CURRENT_MAX_MA: MotorLimit(type=MotorLimit.LIMIT_CURRENT_MAX_MA, value=150.0),
            MotorLimit.LIMIT_TEMPERATURE_MAX_C: MotorLimit(type=MotorLimit.LIMIT_TEMPERATURE_MAX_C, value=70.0),
        },
        variant="STS3215-C002",
        description="STS3215 SO-100 variant C002",
        encoder_resolution=4096.0,
        position_to_radian_ratio=(2 * math.pi) / 4096,
        velocity_ratio=(2 * math.pi) / 4096,
        current_unit_ma_per_bit=6.5,
        voltage_unit_v_per_bit=0.1,
        temperature_unit_c_per_bit=1.0,
        acceleration_unit_rad_s2_per_bit=None,
        gear_ratio=1.0,
        brand=MotorBrand.FEETECH,
    ),
    MotorModelInfo(
        model="STS3215",
        model_ids=[3215, 1545, 0x0C8F],  # Same as base model
        limits={
            MotorLimit.LIMIT_VOLTAGE_MIN: MotorLimit(type=MotorLimit.LIMIT_VOLTAGE_MIN, value=4.0),
            MotorLimit.LIMIT_VOLTAGE_MAX: MotorLimit(type=MotorLimit.LIMIT_VOLTAGE_MAX, value=8.0),
            MotorLimit.LIMIT_CURRENT_MAX_MA: MotorLimit(type=MotorLimit.LIMIT_CURRENT_MAX_MA, value=150.0),
            MotorLimit.LIMIT_TEMPERATURE_MAX_C: MotorLimit(type=MotorLimit.LIMIT_TEMPERATURE_MAX_C, value=70.0),
        },
        variant="STS3215-C044",
        description="STS3215 SO-101 variant C044",
        encoder_resolution=4096.0,
        position_to_radian_ratio=(2 * math.pi) / 4096,
        velocity_ratio=(2 * math.pi) / 4096,
        current_unit_ma_per_bit=6.5,
        voltage_unit_v_per_bit=0.1,
        temperature_unit_c_per_bit=1.0,
        acceleration_unit_rad_s2_per_bit=None,
        gear_ratio=1.0,
        brand=MotorBrand.FEETECH,
    ),
    MotorModelInfo(
        model="STS3215",
        model_ids=[3215, 1545, 0x0C8F],  # Same as base model
        limits={
            MotorLimit.LIMIT_VOLTAGE_MIN: MotorLimit(type=MotorLimit.LIMIT_VOLTAGE_MIN, value=4.0),
            MotorLimit.LIMIT_VOLTAGE_MAX: MotorLimit(type=MotorLimit.LIMIT_VOLTAGE_MAX, value=8.0),
            MotorLimit.LIMIT_CURRENT_MAX_MA: MotorLimit(type=MotorLimit.LIMIT_CURRENT_MAX_MA, value=150.0),
            MotorLimit.LIMIT_TEMPERATURE_MAX_C: MotorLimit(type=MotorLimit.LIMIT_TEMPERATURE_MAX_C, value=70.0),
        },
        variant="STS3215-C046",
        description="STS3215 SO-101 variant C046",
        encoder_resolution=4096.0,
        position_to_radian_ratio=(2 * math.pi) / 4096,
        velocity_ratio=(2 * math.pi) / 4096,
        current_unit_ma_per_bit=6.5,
        voltage_unit_v_per_bit=0.1,
        temperature_unit_c_per_bit=1.0,
        acceleration_unit_rad_s2_per_bit=None,
        gear_ratio=1.0,
        brand=MotorBrand.FEETECH,
    ),
    MotorModelInfo(
        model="STS3032",
        model_ids=[777],
        limits={
            MotorLimit.LIMIT_VOLTAGE_MIN: MotorLimit(type=MotorLimit.LIMIT_VOLTAGE_MIN, value=5.5),
            MotorLimit.LIMIT_VOLTAGE_MAX: MotorLimit(type=MotorLimit.LIMIT_VOLTAGE_MAX, value=12.6),
            MotorLimit.LIMIT_CURRENT_MAX_MA: MotorLimit(type=MotorLimit.LIMIT_CURRENT_MAX_MA, value=1000.0),
            MotorLimit.LIMIT_TEMPERATURE_MAX_C: MotorLimit(type=MotorLimit.LIMIT_TEMPERATURE_MAX_C, value=80.0),
        },
        variant=None,
        description="STS3032 high speed/torque",
        encoder_resolution=4096.0,
        position_to_radian_ratio=(2 * math.pi) / 4096,
        velocity_ratio=(2 * math.pi) / 4096,
        current_unit_ma_per_bit=6.5,
        voltage_unit_v_per_bit=0.1,
        temperature_unit_c_per_bit=1.0,
        acceleration_unit_rad_s2_per_bit=None,
        gear_ratio=1.0,
        brand=MotorBrand.FEETECH,
    ),
    # SCS series models
    MotorModelInfo(
        model="SCS0009",
        model_ids=[9],
        limits={
            MotorLimit.LIMIT_VOLTAGE_MIN: MotorLimit(type=MotorLimit.LIMIT_VOLTAGE_MIN, value=4.8),
            MotorLimit.LIMIT_VOLTAGE_MAX: MotorLimit(type=MotorLimit.LIMIT_VOLTAGE_MAX, value=7.4),
            MotorLimit.LIMIT_CURRENT_MAX_MA: MotorLimit(type=MotorLimit.LIMIT_CURRENT_MAX_MA, value=500.0),
            MotorLimit.LIMIT_TEMPERATURE_MAX_C: MotorLimit(type=MotorLimit.LIMIT_TEMPERATURE_MAX_C, value=80.0),
        },
        variant=None,
        description="SCS0009 micro-servo",
        encoder_resolution=1024.0,
        position_to_radian_ratio=(2 * math.pi) / 1024,
        velocity_ratio=(2 * math.pi) / 1024,
        current_unit_ma_per_bit=6.5,
        voltage_unit_v_per_bit=0.1,
        temperature_unit_c_per_bit=1.0,
        acceleration_unit_rad_s2_per_bit=None,
        gear_ratio=1.0,
        brand=MotorBrand.FEETECH,
    ),
    # Legacy models for compatibility
    MotorModelInfo(
        model="SM8512BL",
        model_ids=[8512],  # Placeholder model_id
        limits={
            MotorLimit.LIMIT_VOLTAGE_MIN: MotorLimit(type=MotorLimit.LIMIT_VOLTAGE_MIN, value=4.8),
            MotorLimit.LIMIT_VOLTAGE_MAX: MotorLimit(type=MotorLimit.LIMIT_VOLTAGE_MAX, value=7.4),
            MotorLimit.LIMIT_CURRENT_MAX_MA: MotorLimit(type=MotorLimit.LIMIT_CURRENT_MAX_MA, value=1000.0),
            MotorLimit.LIMIT_TEMPERATURE_MAX_C: MotorLimit(type=MotorLimit.LIMIT_TEMPERATURE_MAX_C, value=80.0),
        },
        variant=None,
        description="SM8512BL servo motor (legacy)",
        encoder_resolution=4096.0,
        position_to_radian_ratio=(2 * math.pi)
        / 4096,  # Feetech uses 4096-count encoder: multiply by (2π/4096) to convert counts to radians
        velocity_ratio=(2 * math.pi)
        / 4096,  # Feetech reports velocity in counts/s: multiply by (2π/4096) to convert to rad/s
        current_unit_ma_per_bit=6.5,
        voltage_unit_v_per_bit=0.1,
        temperature_unit_c_per_bit=1.0,
        acceleration_unit_rad_s2_per_bit=None,
        gear_ratio=1.0,
        brand=MotorBrand.FEETECH,
    ),
    MotorModelInfo(
        model="ST3225",
        model_ids=[3225],  # Placeholder model_id
        limits={
            MotorLimit.LIMIT_VOLTAGE_MIN: MotorLimit(type=MotorLimit.LIMIT_VOLTAGE_MIN, value=4.8),
            MotorLimit.LIMIT_VOLTAGE_MAX: MotorLimit(type=MotorLimit.LIMIT_VOLTAGE_MAX, value=7.4),
            MotorLimit.LIMIT_CURRENT_MAX_MA: MotorLimit(type=MotorLimit.LIMIT_CURRENT_MAX_MA, value=1000.0),
            MotorLimit.LIMIT_TEMPERATURE_MAX_C: MotorLimit(type=MotorLimit.LIMIT_TEMPERATURE_MAX_C, value=80.0),
        },
        variant=None,
        description="ST3225 servo motor (legacy)",
        encoder_resolution=4096.0,
        position_to_radian_ratio=(2 * math.pi)
        / 4096,  # Feetech uses 4096-count encoder: multiply by (2π/4096) to convert counts to radians
        velocity_ratio=(2 * math.pi)
        / 4096,  # Feetech reports velocity in counts/s: multiply by (2π/4096) to convert to rad/s
        current_unit_ma_per_bit=6.5,
        voltage_unit_v_per_bit=0.1,
        temperature_unit_c_per_bit=1.0,
        acceleration_unit_rad_s2_per_bit=None,
        gear_ratio=1.0,
        brand=MotorBrand.FEETECH,
    ),
]

# Consolidated convenience list of all Feetech models across series
FEETECH_MODELS_LIST: list[MotorModelInfo] = SCS_STS_MODELS_LIST

# Per-model supported register groups
# Each entry: (set of model base names), set of supported register addresses (int)
# Use lowercase model names for matching; matching is strict (no variant stripping).
FEETECH_REGISTER_SUPPORT: list[tuple[set[str], set[int]]] = [
    (
        {
            "sts3215",
            "sts3032",
            "sts3250",
            "st3225",
            "sm8512bl",
        },
        {
            SCS_STS_Registers.HOMING_OFFSET[0],
            SCS_STS_Registers.RANGE_MIN[0],
            SCS_STS_Registers.RANGE_MAX[0],
            SCS_STS_Registers.PRESENT_POSITION[0],
            SCS_STS_Registers.PRESENT_VELOCITY[0],
            SCS_STS_Registers.PRESENT_LOAD[0],
            SCS_STS_Registers.PRESENT_VOLTAGE[0],
            SCS_STS_Registers.PRESENT_TEMPERATURE[0],
            SCS_STS_Registers.PRESENT_CURRENT[0],
            SCS_STS_Registers.GOAL_POSITION[0],
        },
    ),
    (
        {"scs0009"},
        {
            SCS_STS_Registers.RANGE_MIN[0],
            SCS_STS_Registers.RANGE_MAX[0],
            SCS_STS_Registers.PRESENT_POSITION[0],
            SCS_STS_Registers.PRESENT_VELOCITY[0],
            SCS_STS_Registers.PRESENT_LOAD[0],
            SCS_STS_Registers.PRESENT_VOLTAGE[0],
            SCS_STS_Registers.PRESENT_TEMPERATURE[0],
            SCS_STS_Registers.PRESENT_CURRENT[0],
            SCS_STS_Registers.GOAL_POSITION[0],
        },
    ),
]


def feetech_supports_register(model_name: str, register_addr: int) -> bool:
    """Return True if the given Feetech `register_addr` is supported for `model_name`.

    Matching is strict: `model_name` must match one of the base model names in
    `FEETECH_REGISTER_SUPPORT` (case-insensitive). Unknown models return False.
    """
    m = model_name.lower()
    for models_set, addrs in FEETECH_REGISTER_SUPPORT:
        if m in models_set:
            return register_addr in addrs
    return False


# Register models for global lookup
try:
    from ..base import MotorUtil

    MotorUtil.register_models(FEETECH_MODELS_LIST)
except Exception:
    pass


def models_for_id(model_id: int) -> list[MotorModelInfo]:
    """Return all `MotorModelInfo` entries across Feetech series that include
    `model_id` in their `model_ids`."""
    results: list[MotorModelInfo] = []
    for m in SCS_STS_MODELS_LIST:
        if int(model_id) in (m.model_ids or []):
            results.append(m)
    return results
