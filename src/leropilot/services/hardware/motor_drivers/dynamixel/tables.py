"""Dynamixel protocol model tables and helpers.

This file centralizes model metadata for Dynamixel Protocol 2.0 motors.
Drivers should import `DYNAMIXEL_MODELS_LIST` and use `models_for_id` /
`select_model_for_number` helpers for identification and lookups.
"""

from __future__ import annotations

import math

from leropilot.models.hardware import MotorBrand, MotorLimit, MotorModelInfo


class DynamixelRegisters:
    """Dynamixel Protocol 2.0 control table addresses (EEPROM and RAM areas)."""

    # Control table registers as (address, length)
    MODEL_NUMBER = (0, 2)
    FIRMWARE = (6, 1)
    TORQUE_ENABLE = (64, 1)
    GOAL_POSITION = (116, 4)
    GOAL_VELOCITY = (104, 4)
    PROFILE_VELOCITY = (112, 4)
    GOAL_CURRENT = (102, 2)
    PRESENT_POSITION = (132, 4)
    PRESENT_VELOCITY = (128, 4)
    PRESENT_CURRENT = (126, 2)
    PRESENT_VOLTAGE = (144, 2)
    PRESENT_TEMPERATURE = (146, 1)

    # Additional configuration registers
    OPERATING_MODE = (11, 1)
    DRIVE_MODE = (10, 1)
    CURRENT_LIMIT = (38, 2)
    VELOCITY_LIMIT = (44, 4)
    MAX_POSITION_LIMIT = (48, 4)
    MIN_POSITION_LIMIT = (52, 4)
    ACCELERATION_LIMIT = (40, 4)
    TEMPERATURE_LIMIT = (31, 1)

    # Homing/range register addresses (from lerobot / protocol docs)
    HOMING_OFFSET = (20, 4)
    RANGE_MIN = (52, 4)
    RANGE_MAX = (48, 4)


class DynamixelUnits:
    """Unit conversion factors for Dynamixel Protocol 2.0.

    Based on X-series (XM/XH/XW/XC) specifications.
    Different models may have different conversion factors.
    """

    # Current: 2.69mA per unit (for XM430/XH430/XH540)
    # Some models use 3.36mA per unit (check motor manual)
    CURRENT_MA_PER_UNIT = 2.69  # Default for X-series

    # Velocity: 0.229 rpm per unit for X-series
    # Convert to rad/s: (0.229 rpm) * (2π/60) = 0.02398 rad/s per unit
    VELOCITY_RPM_PER_UNIT = 0.229
    VELOCITY_RAD_S_PER_UNIT = VELOCITY_RPM_PER_UNIT * (2 * math.pi / 60)

    # Acceleration: 214.577 rev/min² per unit
    # Convert to rad/s²: (214.577 rev/min²) * (2π/60²) = 0.3738 rad/s² per unit
    ACCELERATION_REV_MIN2_PER_UNIT = 214.577
    ACCELERATION_RAD_S2_PER_UNIT = ACCELERATION_REV_MIN2_PER_UNIT * (2 * math.pi / 3600)

    # Temperature: 1°C per unit (direct mapping)
    TEMPERATURE_C_PER_UNIT = 1.0

    # Voltage: 0.1V per unit
    VOLTAGE_V_PER_UNIT = 0.1


# Registers that need signed interpretation (two's complement)
# Based on lerobot's X_SERIES_ENCODINGS_TABLE
SIGNED_REGISTERS: dict[int, int] = {
    DynamixelRegisters.HOMING_OFFSET[0]: 4,  # 32-bit signed
    DynamixelRegisters.GOAL_POSITION[0]: 4,  # 32-bit signed (extended position)
    DynamixelRegisters.PRESENT_POSITION[0]: 4,  # 32-bit signed (extended position)
    DynamixelRegisters.GOAL_VELOCITY[0]: 4,  # 32-bit signed
    DynamixelRegisters.PRESENT_VELOCITY[0]: 4,  # 32-bit signed
    DynamixelRegisters.GOAL_CURRENT[0]: 2,  # 16-bit signed
    DynamixelRegisters.PRESENT_CURRENT[0]: 2,  # 16-bit signed
}


# Protocol 2.0 motor models only
# Each entry lists model_ids (as model number) and optional variant string.
# Protocol 1.0 motors (AX/old MX/XL320) are NOT supported - they use different register addresses.

DYNAMIXEL_MODELS_LIST: list[MotorModelInfo] = [
    # MX Series (Protocol 2.0 versions only)
    MotorModelInfo(
        model="MX-28",
        model_ids=[30],
        limits={},
        encoder_resolution=4096.0,
        variant="2.0",
        position_to_radian_ratio=(2 * math.pi) / 4096,
        velocity_ratio=0.229,  #  * 2 * math.pi / 60,
        current_unit_ma_per_bit=2.69,
        voltage_unit_v_per_bit=0.1,
        temperature_unit_c_per_bit=1.0,
        acceleration_unit_rad_s2_per_bit=0.3738,
        brand=MotorBrand.DYNAMIXEL,
    ),
    MotorModelInfo(
        model="MX-64",
        model_ids=[311],
        limits={},
        encoder_resolution=4096.0,
        variant="2.0",
        position_to_radian_ratio=(2 * math.pi) / 4096,
        velocity_ratio=0.229,  #  * 2 * math.pi / 60,
        current_unit_ma_per_bit=2.69,
        voltage_unit_v_per_bit=0.1,
        temperature_unit_c_per_bit=1.0,
        acceleration_unit_rad_s2_per_bit=0.3738,
        brand=MotorBrand.DYNAMIXEL,
    ),
    MotorModelInfo(
        model="MX-106",
        model_ids=[321],
        limits={},
        encoder_resolution=4096.0,
        variant="2.0",
        position_to_radian_ratio=(2 * math.pi) / 4096,
        velocity_ratio=0.229,  #  * 2 * math.pi / 60,
        current_unit_ma_per_bit=2.69,
        voltage_unit_v_per_bit=0.1,
        temperature_unit_c_per_bit=1.0,
        acceleration_unit_rad_s2_per_bit=0.3738,
        brand=MotorBrand.DYNAMIXEL,
    ),
    # X Series (all use Protocol 2.0)
    MotorModelInfo(
        model="XM430",
        model_ids=[1020, 1050],
        limits={
            MotorLimit.LIMIT_VOLTAGE_MIN: MotorLimit(type=MotorLimit.LIMIT_VOLTAGE_MIN, value=10.0),
            MotorLimit.LIMIT_VOLTAGE_MAX: MotorLimit(type=MotorLimit.LIMIT_VOLTAGE_MAX, value=14.8),
            MotorLimit.LIMIT_CURRENT_MAX_MA: MotorLimit(type=MotorLimit.LIMIT_CURRENT_MAX_MA, value=2300.0),
            MotorLimit.LIMIT_TEMPERATURE_MAX_C: MotorLimit(type=MotorLimit.LIMIT_TEMPERATURE_MAX_C, value=80.0),
        },
        encoder_resolution=4096.0,
        variant="W350",
        position_to_radian_ratio=(2 * math.pi) / 4096,
        velocity_ratio=0.229,  #  * 2 * math.pi / 60,
        current_unit_ma_per_bit=2.69,
        voltage_unit_v_per_bit=0.1,
        temperature_unit_c_per_bit=1.0,
        acceleration_unit_rad_s2_per_bit=0.3738,
        brand=MotorBrand.DYNAMIXEL,
    ),
    MotorModelInfo(
        model="XM430",
        model_ids=[1030, 1040],
        limits={
            MotorLimit.LIMIT_VOLTAGE_MIN: MotorLimit(type=MotorLimit.LIMIT_VOLTAGE_MIN, value=10.0),
            MotorLimit.LIMIT_VOLTAGE_MAX: MotorLimit(type=MotorLimit.LIMIT_VOLTAGE_MAX, value=14.8),
            MotorLimit.LIMIT_CURRENT_MAX_MA: MotorLimit(type=MotorLimit.LIMIT_CURRENT_MAX_MA, value=2300.0),
            MotorLimit.LIMIT_TEMPERATURE_MAX_C: MotorLimit(type=MotorLimit.LIMIT_TEMPERATURE_MAX_C, value=80.0),
        },
        encoder_resolution=4096.0,
        variant="W210",
        position_to_radian_ratio=(2 * math.pi) / 4096,
        velocity_ratio=0.229,  #  * 2 * math.pi / 60,
        current_unit_ma_per_bit=2.69,
        voltage_unit_v_per_bit=0.1,
        temperature_unit_c_per_bit=1.0,
        acceleration_unit_rad_s2_per_bit=0.3738,
        brand=MotorBrand.DYNAMIXEL,
    ),
    MotorModelInfo(
        model="XL430",
        model_ids=[1060],
        limits={
            MotorLimit.LIMIT_VOLTAGE_MIN: MotorLimit(type=MotorLimit.LIMIT_VOLTAGE_MIN, value=6.5),
            MotorLimit.LIMIT_VOLTAGE_MAX: MotorLimit(type=MotorLimit.LIMIT_VOLTAGE_MAX, value=12.0),
            MotorLimit.LIMIT_CURRENT_MAX_MA: MotorLimit(type=MotorLimit.LIMIT_CURRENT_MAX_MA, value=1000.0),
            MotorLimit.LIMIT_TEMPERATURE_MAX_C: MotorLimit(type=MotorLimit.LIMIT_TEMPERATURE_MAX_C, value=72.0),
        },
        encoder_resolution=4096.0,
        variant="W250",
        position_to_radian_ratio=(2 * math.pi) / 4096,
        velocity_ratio=0.229,  #  * 2 * math.pi / 60,
        current_unit_ma_per_bit=2.69,
        voltage_unit_v_per_bit=0.1,
        temperature_unit_c_per_bit=1.0,
        acceleration_unit_rad_s2_per_bit=0.3738,
        brand=MotorBrand.DYNAMIXEL,
    ),
    MotorModelInfo(
        model="XC430",
        model_ids=[1070],
        limits={
            MotorLimit.LIMIT_VOLTAGE_MIN: MotorLimit(type=MotorLimit.LIMIT_VOLTAGE_MIN, value=6.5),
            MotorLimit.LIMIT_VOLTAGE_MAX: MotorLimit(type=MotorLimit.LIMIT_VOLTAGE_MAX, value=14.8),
            MotorLimit.LIMIT_CURRENT_MAX_MA: MotorLimit(type=MotorLimit.LIMIT_CURRENT_MAX_MA, value=1000.0),
            MotorLimit.LIMIT_TEMPERATURE_MAX_C: MotorLimit(type=MotorLimit.LIMIT_TEMPERATURE_MAX_C, value=80.0),
        },
        encoder_resolution=4096.0,
        variant="W150",
        position_to_radian_ratio=(2 * math.pi) / 4096,
        velocity_ratio=0.229,  #  * 2 * math.pi / 60,
        current_unit_ma_per_bit=2.69,
        voltage_unit_v_per_bit=0.1,
        temperature_unit_c_per_bit=1.0,
        acceleration_unit_rad_s2_per_bit=0.3738,
        brand=MotorBrand.DYNAMIXEL,
    ),
    MotorModelInfo(
        model="XC330",
        model_ids=[1090],
        limits={},
        encoder_resolution=4096.0,
        variant="T288",
        position_to_radian_ratio=(2 * math.pi) / 4096,
        velocity_ratio=0.229,  #  * 2 * math.pi / 60,
        current_unit_ma_per_bit=2.69,
        voltage_unit_v_per_bit=0.1,
        temperature_unit_c_per_bit=1.0,
        acceleration_unit_rad_s2_per_bit=0.3738,
        brand=MotorBrand.DYNAMIXEL,
    ),
    MotorModelInfo(
        model="XC330",
        model_ids=[1100],
        limits={},
        encoder_resolution=4096.0,
        variant="T181",
        position_to_radian_ratio=(2 * math.pi) / 4096,
        velocity_ratio=0.229,  #  * 2 * math.pi / 60,
        current_unit_ma_per_bit=2.69,
        voltage_unit_v_per_bit=0.1,
        temperature_unit_c_per_bit=1.0,
        acceleration_unit_rad_s2_per_bit=0.3738,
        brand=MotorBrand.DYNAMIXEL,
    ),
    MotorModelInfo(
        model="XC330",
        model_ids=[1130],
        limits={},
        encoder_resolution=4096.0,
        variant="M181",
        position_to_radian_ratio=(2 * math.pi) / 4096,
        velocity_ratio=0.229,  #  * 2 * math.pi / 60,
        current_unit_ma_per_bit=2.69,
        voltage_unit_v_per_bit=0.1,
        temperature_unit_c_per_bit=1.0,
        acceleration_unit_rad_s2_per_bit=0.3738,
        brand=MotorBrand.DYNAMIXEL,
    ),
    MotorModelInfo(
        model="XM540",
        model_ids=[1120, 1210],
        limits={},
        encoder_resolution=4096.0,
        variant="W270",
        position_to_radian_ratio=(2 * math.pi) / 4096,
        velocity_ratio=0.229,  #  * 2 * math.pi / 60,
        current_unit_ma_per_bit=2.69,
        voltage_unit_v_per_bit=0.1,
        temperature_unit_c_per_bit=1.0,
        acceleration_unit_rad_s2_per_bit=0.3738,
        brand=MotorBrand.DYNAMIXEL,
    ),
    # Base entries (aggregate variants) for convenient lookup by base model
    MotorModelInfo(
        model="XM430",
        model_ids=[1020, 1050, 1030, 1040],
        limits={},
        encoder_resolution=4096.0,
        variant=None,
        position_to_radian_ratio=(2 * math.pi) / 4096,
        velocity_ratio=0.229,  #  * 2 * math.pi / 60,
        current_unit_ma_per_bit=2.69,
        voltage_unit_v_per_bit=0.1,
        temperature_unit_c_per_bit=1.0,
        acceleration_unit_rad_s2_per_bit=0.3738,
        brand=MotorBrand.DYNAMIXEL,
    ),
    MotorModelInfo(
        model="XL430",
        model_ids=[1060],
        limits={},
        encoder_resolution=4096.0,
        variant=None,
        position_to_radian_ratio=(2 * math.pi) / 4096,
        velocity_ratio=0.229,  #  * 2 * math.pi / 60,
        current_unit_ma_per_bit=2.69,
        voltage_unit_v_per_bit=0.1,
        temperature_unit_c_per_bit=1.0,
        acceleration_unit_rad_s2_per_bit=0.3738,
        brand=MotorBrand.DYNAMIXEL,
    ),
    MotorModelInfo(
        model="XC330",
        model_ids=[1090, 1100, 1130],
        limits={},
        encoder_resolution=4096.0,
        variant=None,
        position_to_radian_ratio=(2 * math.pi) / 4096,
        velocity_ratio=0.229,  #  * 2 * math.pi / 60,
        current_unit_ma_per_bit=2.69,
        voltage_unit_v_per_bit=0.1,
        temperature_unit_c_per_bit=1.0,
        acceleration_unit_rad_s2_per_bit=0.3738,
        brand=MotorBrand.DYNAMIXEL,
    ),
    MotorModelInfo(
        model="XM540",
        model_ids=[1120, 1210],
        limits={},
        encoder_resolution=4096.0,
        variant=None,
        position_to_radian_ratio=(2 * math.pi) / 4096,
        velocity_ratio=0.229,  #  * 2 * math.pi / 60,
        current_unit_ma_per_bit=2.69,
        voltage_unit_v_per_bit=0.1,
        temperature_unit_c_per_bit=1.0,
        acceleration_unit_rad_s2_per_bit=0.3738,
        brand=MotorBrand.DYNAMIXEL,
    ),
    MotorModelInfo(
        model="XL330",
        model_ids=[1190, 1200],
        limits={},
        encoder_resolution=4096.0,
        variant=None,
        position_to_radian_ratio=(2 * math.pi) / 4096,
        velocity_ratio=0.229,  #  * 2 * math.pi / 60,
        current_unit_ma_per_bit=3.36,
        voltage_unit_v_per_bit=0.1,
        temperature_unit_c_per_bit=1.0,
        acceleration_unit_rad_s2_per_bit=0.3738,
        brand=MotorBrand.DYNAMIXEL,
    ),
    MotorModelInfo(
        model="XL330",
        model_ids=[1190],
        limits={
            MotorLimit.LIMIT_VOLTAGE_MIN: MotorLimit(type=MotorLimit.LIMIT_VOLTAGE_MIN, value=3.7),
            MotorLimit.LIMIT_VOLTAGE_MAX: MotorLimit(type=MotorLimit.LIMIT_VOLTAGE_MAX, value=6.0),
            MotorLimit.LIMIT_CURRENT_MAX_MA: MotorLimit(type=MotorLimit.LIMIT_CURRENT_MAX_MA, value=400.0),
            MotorLimit.LIMIT_TEMPERATURE_MAX_C: MotorLimit(type=MotorLimit.LIMIT_TEMPERATURE_MAX_C, value=60.0),
        },
        encoder_resolution=4096.0,
        variant="M077",
        position_to_radian_ratio=(2 * math.pi) / 4096,
        velocity_ratio=0.229,  #  * 2 * math.pi / 60,
        current_unit_ma_per_bit=3.36,
        voltage_unit_v_per_bit=0.1,
        temperature_unit_c_per_bit=1.0,
        acceleration_unit_rad_s2_per_bit=0.3738,
        brand=MotorBrand.DYNAMIXEL,
    ),
    MotorModelInfo(
        model="XL330",
        model_ids=[1200],
        limits={
            MotorLimit.LIMIT_VOLTAGE_MIN: MotorLimit(type=MotorLimit.LIMIT_VOLTAGE_MIN, value=3.7),
            MotorLimit.LIMIT_VOLTAGE_MAX: MotorLimit(type=MotorLimit.LIMIT_VOLTAGE_MAX, value=6.0),
            MotorLimit.LIMIT_CURRENT_MAX_MA: MotorLimit(type=MotorLimit.LIMIT_CURRENT_MAX_MA, value=400.0),
            MotorLimit.LIMIT_TEMPERATURE_MAX_C: MotorLimit(type=MotorLimit.LIMIT_TEMPERATURE_MAX_C, value=60.0),
        },
        encoder_resolution=4096.0,
        variant="M288",
        position_to_radian_ratio=(2 * math.pi) / 4096,
        velocity_ratio=0.229,  #  * 2 * math.pi / 60,
        current_unit_ma_per_bit=3.36,
        voltage_unit_v_per_bit=0.1,
        temperature_unit_c_per_bit=1.0,
        acceleration_unit_rad_s2_per_bit=0.3738,
        brand=MotorBrand.DYNAMIXEL,
    ),
]


# Per-model supported register groups
# Each entry: (set of model base names), set of supported register addresses (int)
# Use lowercase model names for matching; matching is strict (no variant stripping).
DYNAMIXEL_REGISTER_SUPPORT: list[tuple[set[str], set[int]]] = [
    (
        {
            "xm430",
            "xl430",
            "xm540",
            "xl330",
            "xc430",
            "xc330",
            "xl320",
            "mx-28",
            "mx-64",
            "mx-106",
        },
        {
            DynamixelRegisters.HOMING_OFFSET[0],
            DynamixelRegisters.RANGE_MIN[0],
            DynamixelRegisters.RANGE_MAX[0],
            DynamixelRegisters.PRESENT_POSITION[0],
            DynamixelRegisters.PRESENT_VELOCITY[0],
            DynamixelRegisters.PRESENT_CURRENT[0],
            DynamixelRegisters.PRESENT_VOLTAGE[0],
            DynamixelRegisters.PRESENT_TEMPERATURE[0],
            DynamixelRegisters.GOAL_POSITION[0],
            DynamixelRegisters.GOAL_VELOCITY[0],
            DynamixelRegisters.GOAL_CURRENT[0],
        },
    ),
]


def dynamixel_supports_register(model_name: str, register_addr: int) -> bool:
    """Return True if the given Dynamixel `register_addr` is supported for `model_name`.

    Matching is strict: `model_name` must match one of the base model names in
    `DYNAMIXEL_REGISTER_SUPPORT` (case-insensitive). Unknown models return False.
    """
    m = model_name.lower()
    for models_set, addrs in DYNAMIXEL_REGISTER_SUPPORT:
        if m in models_set:
            return register_addr in addrs
    return False


def models_for_id(model_id: int) -> list[MotorModelInfo]:
    """Return all MotorModelInfo entries that include `model_id` in their model_ids."""
    return [m for m in DYNAMIXEL_MODELS_LIST if int(model_id) in (m.model_ids or [])]


# Register models for global lookup
try:
    from ..base import MotorUtil

    MotorUtil.register_models(DYNAMIXEL_MODELS_LIST)
except Exception:
    pass


# Helper to select best candidate (prefers base model when ambiguous)
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
    # prefer a specific variant when available (e.g., M077 vs aggregate base)
    for c in candidates:
        if c.variant is not None:
            return c
    # if no specific variant, fall back to base (variant == None)
    for c in candidates:
        if c.variant is None:
            return c
    # otherwise return first
    return candidates[0]
