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


# Signed register encoding table for sign-magnitude conversion
# Maps register address to sign bit position
# Feetech motors use sign-magnitude encoding (not two's complement)
# For 16-bit values: sign bit is at position 15
# For 12-bit values: sign bit is at position 11
SIGNED_REGISTERS: dict[int, int] = {
    SCS_STS_Registers.PRESENT_POSITION[0]: 15,  # 16-bit sign-magnitude (direction bit)
    SCS_STS_Registers.GOAL_POSITION[0]: 15,  # 16-bit sign-magnitude (direction bit)
    SCS_STS_Registers.PRESENT_VELOCITY[0]: 15,  # 16-bit sign-magnitude
    SCS_STS_Registers.PRESENT_LOAD[0]: 15,  # 16-bit sign-magnitude
    SCS_STS_Registers.PRESENT_CURRENT[0]: 15,  # 16-bit sign-magnitude
    SCS_STS_Registers.HOMING_OFFSET[0]: 11,  # 12-bit sign-magnitude
    SCS_STS_Registers.GOAL_VELOCITY[0]: 15,  # 16-bit sign-magnitude
}


# Model definitions for Feetech motors (STS/SCS families).
# Each entry is a separate MotorModelInfo with model_ids and limits populated.


SCS_STS_MODELS_LIST: list[MotorModelInfo] = [
    MotorModelInfo(
        model="Feetech",
        model_ids=[],
        limits={
            MotorLimit.LIMIT_CURRENT_MAX_MA: MotorLimit(type=MotorLimit.LIMIT_CURRENT_MAX_MA, value=150.0),
            MotorLimit.LIMIT_TEMPERATURE_MAX_C: MotorLimit(type=MotorLimit.LIMIT_TEMPERATURE_MAX_C, value=70.0),
        },
        variant=None,
        description="Feetech generic motor",
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
]

# Consolidated convenience list of all Feetech models across series
FEETECH_MODELS_LIST: list[MotorModelInfo] = SCS_STS_MODELS_LIST

# Per-model supported register groups
# Each entry: (set of model base names), set of supported register addresses (int)
# Use lowercase model names for matching; matching is strict (no variant stripping).
FEETECH_REGISTER_SUPPORT: list[tuple[set[str], set[int]]] = [
    (
        {
            "feetech",
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
    """Return the generic Feetech model.
    
    Since Feetech motors do not provide reliable model number information,
    we return the generic model descriptor instead of trying to match
    specific models by ID.
    """
    # Always return the generic Feetech model (first and only model in the list)
    return [SCS_STS_MODELS_LIST[0]]
