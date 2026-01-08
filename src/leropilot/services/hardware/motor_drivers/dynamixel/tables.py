"""Dynamixel protocol model tables and helpers.

This file centralizes model metadata for Dynamixel Protocol 2.0 motors.
Drivers should import `DYNAMIXEL_MODELS_LIST` and use `models_for_id` /
`select_model_for_number` helpers for identification and lookups.
"""

from __future__ import annotations

from leropilot.models.hardware import MotorBrand, MotorLimit, MotorLimitTypes, MotorModelInfo


class DynamixelRegisters:
    """Dynamixel Protocol 2.0 control table addresses (EEPROM and RAM areas)."""

    # Control table addresses
    ADDR_MODEL_NUMBER = 0
    ADDR_FIRMWARE = 6
    ADDR_TORQUE_ENABLE = 64
    ADDR_GOAL_POSITION = 116
    ADDR_GOAL_VELOCITY = 104
    ADDR_GOAL_CURRENT = 102
    ADDR_PRESENT_POSITION = 132
    ADDR_PRESENT_VELOCITY = 128
    ADDR_PRESENT_CURRENT = 126
    ADDR_PRESENT_VOLTAGE = 144
    ADDR_PRESENT_TEMPERATURE = 146

    # Register lengths (bytes)
    LEN_MODEL_NUMBER = 2
    LEN_FIRMWARE = 1
    LEN_TORQUE_ENABLE = 1
    LEN_GOAL_POSITION = 4
    LEN_GOAL_VELOCITY = 4
    LEN_GOAL_CURRENT = 2
    LEN_PRESENT_POSITION = 4
    LEN_PRESENT_VELOCITY = 4
    LEN_PRESENT_CURRENT = 2
    LEN_PRESENT_VOLTAGE = 2
    LEN_PRESENT_TEMPERATURE = 1


# Minimal model list derived from inline MODEL_NUMBER_MAP in the driver.
# Each entry lists model_ids (as model number) and optional variant string.

DYNAMIXEL_MODELS_LIST: list[MotorModelInfo] = [
    MotorModelInfo(model="AX-12A", model_ids=[1], limits={}, variant=None, brand=MotorBrand.DYNAMIXEL),
    MotorModelInfo(model="AX-12+", model_ids=[12], limits={}, variant=None, brand=MotorBrand.DYNAMIXEL),
    MotorModelInfo(model="AX-18A", model_ids=[18], limits={}, variant=None, brand=MotorBrand.DYNAMIXEL),
    MotorModelInfo(model="AX-12W", model_ids=[300], limits={}, variant=None, brand=MotorBrand.DYNAMIXEL),
    MotorModelInfo(model="MX-28", model_ids=[29], limits={}, variant=None, brand=MotorBrand.DYNAMIXEL),
    MotorModelInfo(model="MX-28-2.0", model_ids=[30], limits={}, variant=None, brand=MotorBrand.DYNAMIXEL),
    MotorModelInfo(model="MX-64", model_ids=[310], limits={}, variant=None, brand=MotorBrand.DYNAMIXEL),
    MotorModelInfo(model="MX-64-2.0", model_ids=[311], limits={}, variant=None, brand=MotorBrand.DYNAMIXEL),
    MotorModelInfo(model="MX-106", model_ids=[320], limits={}, variant=None, brand=MotorBrand.DYNAMIXEL),
    MotorModelInfo(model="MX-106-2.0", model_ids=[321], limits={}, variant=None, brand=MotorBrand.DYNAMIXEL),
    MotorModelInfo(model="XL320", model_ids=[350], limits={}, variant=None, brand=MotorBrand.DYNAMIXEL),
    MotorModelInfo(
        model="XM430-W350",
        model_ids=[1020, 1050],
        limits={
            MotorLimitTypes.VOLTAGE_MIN: MotorLimit(type=MotorLimitTypes.VOLTAGE_MIN, value=10.0),
            MotorLimitTypes.VOLTAGE_MAX: MotorLimit(type=MotorLimitTypes.VOLTAGE_MAX, value=14.8),
            MotorLimitTypes.CURRENT_MAX_MA: MotorLimit(type=MotorLimitTypes.CURRENT_MAX_MA, value=2300.0),
            MotorLimitTypes.TEMPERATURE_MAX_C: MotorLimit(type=MotorLimitTypes.TEMPERATURE_MAX_C, value=80.0),
        },
        variant=None,
        brand=MotorBrand.DYNAMIXEL,
    ),
    MotorModelInfo(
        model="XM430-W210",
        model_ids=[1030, 1040],
        limits={
            MotorLimitTypes.VOLTAGE_MIN: MotorLimit(type=MotorLimitTypes.VOLTAGE_MIN, value=10.0),
            MotorLimitTypes.VOLTAGE_MAX: MotorLimit(type=MotorLimitTypes.VOLTAGE_MAX, value=14.8),
            MotorLimitTypes.CURRENT_MAX_MA: MotorLimit(type=MotorLimitTypes.CURRENT_MAX_MA, value=2300.0),
            MotorLimitTypes.TEMPERATURE_MAX_C: MotorLimit(type=MotorLimitTypes.TEMPERATURE_MAX_C, value=80.0),
        },
        variant=None,
        brand=MotorBrand.DYNAMIXEL,
    ),
    MotorModelInfo(
        model="XL430-W250",
        model_ids=[1060],
        limits={
            MotorLimitTypes.VOLTAGE_MIN: MotorLimit(type=MotorLimitTypes.VOLTAGE_MIN, value=6.5),
            MotorLimitTypes.VOLTAGE_MAX: MotorLimit(type=MotorLimitTypes.VOLTAGE_MAX, value=12.0),
            MotorLimitTypes.CURRENT_MAX_MA: MotorLimit(type=MotorLimitTypes.CURRENT_MAX_MA, value=1000.0),
            MotorLimitTypes.TEMPERATURE_MAX_C: MotorLimit(type=MotorLimitTypes.TEMPERATURE_MAX_C, value=72.0),
        },
        variant=None,
        brand=MotorBrand.DYNAMIXEL,
    ),
    MotorModelInfo(
        model="XC430-W150",
        model_ids=[1070],
        limits={
            MotorLimitTypes.VOLTAGE_MIN: MotorLimit(type=MotorLimitTypes.VOLTAGE_MIN, value=6.5),
            MotorLimitTypes.VOLTAGE_MAX: MotorLimit(type=MotorLimitTypes.VOLTAGE_MAX, value=14.8),
            MotorLimitTypes.CURRENT_MAX_MA: MotorLimit(type=MotorLimitTypes.CURRENT_MAX_MA, value=1000.0),
            MotorLimitTypes.TEMPERATURE_MAX_C: MotorLimit(type=MotorLimitTypes.TEMPERATURE_MAX_C, value=80.0),
        },
        variant=None,
        brand=MotorBrand.DYNAMIXEL,
    ),
    MotorModelInfo(model="XC330-T288", model_ids=[1090], limits={}, variant=None, brand=MotorBrand.DYNAMIXEL),
    MotorModelInfo(model="XC330-T181", model_ids=[1100], limits={}, variant=None, brand=MotorBrand.DYNAMIXEL),
    MotorModelInfo(model="XC330-M181", model_ids=[1130], limits={}, variant=None, brand=MotorBrand.DYNAMIXEL),
    MotorModelInfo(model="XM540-W270", model_ids=[1120, 1210], limits={}, variant=None, brand=MotorBrand.DYNAMIXEL),
    MotorModelInfo(
        model="XL330-M077",
        model_ids=[1190],
        limits={
            MotorLimitTypes.VOLTAGE_MIN: MotorLimit(type=MotorLimitTypes.VOLTAGE_MIN, value=3.7),
            MotorLimitTypes.VOLTAGE_MAX: MotorLimit(type=MotorLimitTypes.VOLTAGE_MAX, value=6.0),
            MotorLimitTypes.CURRENT_MAX_MA: MotorLimit(type=MotorLimitTypes.CURRENT_MAX_MA, value=400.0),
            MotorLimitTypes.TEMPERATURE_MAX_C: MotorLimit(type=MotorLimitTypes.TEMPERATURE_MAX_C, value=60.0),
        },
        variant=None,
        brand=MotorBrand.DYNAMIXEL,
    ),
    MotorModelInfo(
        model="XL330-M288",
        model_ids=[1200],
        limits={
            MotorLimitTypes.VOLTAGE_MIN: MotorLimit(type=MotorLimitTypes.VOLTAGE_MIN, value=3.7),
            MotorLimitTypes.VOLTAGE_MAX: MotorLimit(type=MotorLimitTypes.VOLTAGE_MAX, value=6.0),
            MotorLimitTypes.CURRENT_MAX_MA: MotorLimit(type=MotorLimitTypes.CURRENT_MAX_MA, value=400.0),
            MotorLimitTypes.TEMPERATURE_MAX_C: MotorLimit(type=MotorLimitTypes.TEMPERATURE_MAX_C, value=60.0),
        },
        variant=None,
        brand=MotorBrand.DYNAMIXEL,
    ),
]


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
    # prefer base (variant == None)
    for c in candidates:
        if c.variant is None:
            return c
    # otherwise return first
    return candidates[0]
