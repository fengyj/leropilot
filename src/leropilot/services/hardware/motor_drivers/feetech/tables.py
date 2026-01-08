"""Feetech series register definitions and model tables (drivers subpackage).

This file centralizes Feetech-specific constants (per-series registers) and
MotorModelInfo entries for the Feetech family. Model definitions include
`model_ids` and `limits` so they are self-contained and do not rely on
`motor_specs.json` at runtime. The legacy compatibility shim under
`services.hardware.feetech_tables` imports this module.
"""

from __future__ import annotations

import math

from leropilot.models.hardware import MotorBrand, MotorLimit, MotorLimitTypes, MotorModelInfo


class SCS_STS_Registers:
    """Registers for the STS/SCS series (uses SCS style addressing)."""

    ADDR_FIRMWARE_MAJOR = 0
    ADDR_FIRMWARE_MINOR = 1
    ADDR_MODEL_NUMBER = 3
    ADDR_ID = 5
    ADDR_BAUD_RATE = 6
    ADDR_TORQUE_ENABLE = 40
    ADDR_GOAL_POSITION = 42
    ADDR_GOAL_SPEED = 46
    ADDR_PRESENT_POSITION = 56
    ADDR_PRESENT_SPEED = 58
    ADDR_PRESENT_LOAD = 60
    ADDR_PRESENT_VOLTAGE = 62
    ADDR_PRESENT_TEMPERATURE = 63
    ADDR_PRESENT_CURRENT = 69


# Model definitions for Feetech motors (STS/SCS families).
# Each entry is a separate MotorModelInfo with model_ids and limits populated.
SCS_STS_MODELS_LIST: list[MotorModelInfo] = [
    # Base model (variant None) - useful when model_id alone doesn't determine variant
    MotorModelInfo(
        model="STS3215",
        model_ids=[3215, 1545, 0x0C8F],
        limits={
            MotorLimitTypes.VOLTAGE_MIN: MotorLimit(type=MotorLimitTypes.VOLTAGE_MIN, value=6.0),
            MotorLimitTypes.VOLTAGE_MAX: MotorLimit(type=MotorLimitTypes.VOLTAGE_MAX, value=7.4),
            MotorLimitTypes.CURRENT_MAX_MA: MotorLimit(type=MotorLimitTypes.CURRENT_MAX_MA, value=150.0),
            MotorLimitTypes.TEMPERATURE_MAX_C: MotorLimit(type=MotorLimitTypes.TEMPERATURE_MAX_C, value=70.0),
        },
        variant=None,
        description="Feetech STS3215 base model (variant unknown)",
        encoder_resolution=4096,
        position_scale=(2 * math.pi) / 4096,
        gear_ratio=1.0,
        brand=MotorBrand.FEETECH,
    ),
    # Specific variants
    MotorModelInfo(
        model="STS3215",
        model_ids=[49153],
        limits={
            MotorLimitTypes.VOLTAGE_MIN: MotorLimit(type=MotorLimitTypes.VOLTAGE_MIN, value=6.0),
            MotorLimitTypes.VOLTAGE_MAX: MotorLimit(type=MotorLimitTypes.VOLTAGE_MAX, value=7.4),
            MotorLimitTypes.CURRENT_MAX_MA: MotorLimit(type=MotorLimitTypes.CURRENT_MAX_MA, value=150.0),
            MotorLimitTypes.TEMPERATURE_MAX_C: MotorLimit(type=MotorLimitTypes.TEMPERATURE_MAX_C, value=70.0),
        },
        variant="STS3215-C001",
        description="STS3215 SO-101 variant C001",
        encoder_resolution=4096,
        position_scale=(2 * math.pi) / 4096,
        gear_ratio=1.0,
        brand=MotorBrand.FEETECH,
    ),
    MotorModelInfo(
        model="STS3215",
        model_ids=[49220, 49222],
        limits={
            MotorLimitTypes.VOLTAGE_MIN: MotorLimit(type=MotorLimitTypes.VOLTAGE_MIN, value=4.0),
            MotorLimitTypes.VOLTAGE_MAX: MotorLimit(type=MotorLimitTypes.VOLTAGE_MAX, value=14.0),
            MotorLimitTypes.CURRENT_MAX_MA: MotorLimit(type=MotorLimitTypes.CURRENT_MAX_MA, value=180.0),
            MotorLimitTypes.TEMPERATURE_MAX_C: MotorLimit(type=MotorLimitTypes.TEMPERATURE_MAX_C, value=60.0),
        },
        variant="STS3215-C018",
        description="STS3215 high performance C018",
        encoder_resolution=4096,
        position_scale=(2 * math.pi) / 4096,
        gear_ratio=1.0,
        brand=MotorBrand.FEETECH,
    ),
    MotorModelInfo(
        model="STS3215",
        model_ids=[3215, 1545, 0x0C8F],  # Same as base model
        limits={
            MotorLimitTypes.VOLTAGE_MIN: MotorLimit(type=MotorLimitTypes.VOLTAGE_MIN, value=6.0),
            MotorLimitTypes.VOLTAGE_MAX: MotorLimit(type=MotorLimitTypes.VOLTAGE_MAX, value=7.4),
            MotorLimitTypes.CURRENT_MAX_MA: MotorLimit(type=MotorLimitTypes.CURRENT_MAX_MA, value=150.0),
            MotorLimitTypes.TEMPERATURE_MAX_C: MotorLimit(type=MotorLimitTypes.TEMPERATURE_MAX_C, value=70.0),
        },
        variant="STS3215-C002",
        description="STS3215 SO-100 variant C002",
        encoder_resolution=4096,
        position_scale=(2 * math.pi) / 4096,
        gear_ratio=1.0,
        brand=MotorBrand.FEETECH,
    ),
    MotorModelInfo(
        model="STS3215",
        model_ids=[3215, 1545, 0x0C8F],  # Same as base model
        limits={
            MotorLimitTypes.VOLTAGE_MIN: MotorLimit(type=MotorLimitTypes.VOLTAGE_MIN, value=4.0),
            MotorLimitTypes.VOLTAGE_MAX: MotorLimit(type=MotorLimitTypes.VOLTAGE_MAX, value=8.0),
            MotorLimitTypes.CURRENT_MAX_MA: MotorLimit(type=MotorLimitTypes.CURRENT_MAX_MA, value=150.0),
            MotorLimitTypes.TEMPERATURE_MAX_C: MotorLimit(type=MotorLimitTypes.TEMPERATURE_MAX_C, value=70.0),
        },
        variant="STS3215-C044",
        description="STS3215 SO-101 variant C044",
        encoder_resolution=4096,
        position_scale=(2 * math.pi) / 4096,
        gear_ratio=1.0,
        brand=MotorBrand.FEETECH,
    ),
    MotorModelInfo(
        model="STS3215",
        model_ids=[3215, 1545, 0x0C8F],  # Same as base model
        limits={
            MotorLimitTypes.VOLTAGE_MIN: MotorLimit(type=MotorLimitTypes.VOLTAGE_MIN, value=4.0),
            MotorLimitTypes.VOLTAGE_MAX: MotorLimit(type=MotorLimitTypes.VOLTAGE_MAX, value=8.0),
            MotorLimitTypes.CURRENT_MAX_MA: MotorLimit(type=MotorLimitTypes.CURRENT_MAX_MA, value=150.0),
            MotorLimitTypes.TEMPERATURE_MAX_C: MotorLimit(type=MotorLimitTypes.TEMPERATURE_MAX_C, value=70.0),
        },
        variant="STS3215-C046",
        description="STS3215 SO-101 variant C046",
        encoder_resolution=4096,
        position_scale=(2 * math.pi) / 4096,
        gear_ratio=1.0,
        brand=MotorBrand.FEETECH,
    ),
    MotorModelInfo(
        model="STS3032",
        model_ids=[777],
        limits={
            MotorLimitTypes.VOLTAGE_MIN: MotorLimit(type=MotorLimitTypes.VOLTAGE_MIN, value=5.5),
            MotorLimitTypes.VOLTAGE_MAX: MotorLimit(type=MotorLimitTypes.VOLTAGE_MAX, value=12.6),
            MotorLimitTypes.CURRENT_MAX_MA: MotorLimit(type=MotorLimitTypes.CURRENT_MAX_MA, value=1000.0),
            MotorLimitTypes.TEMPERATURE_MAX_C: MotorLimit(type=MotorLimitTypes.TEMPERATURE_MAX_C, value=80.0),
        },
        variant=None,
        description="STS3032 high speed/torque",
        encoder_resolution=4096,
        position_scale=(2 * math.pi) / 4096,
        gear_ratio=1.0,
        brand=MotorBrand.FEETECH,
    ),
    # SCS series models
    MotorModelInfo(
        model="SCS0009",
        model_ids=[9],
        limits={
            MotorLimitTypes.VOLTAGE_MIN: MotorLimit(type=MotorLimitTypes.VOLTAGE_MIN, value=4.8),
            MotorLimitTypes.VOLTAGE_MAX: MotorLimit(type=MotorLimitTypes.VOLTAGE_MAX, value=7.4),
            MotorLimitTypes.CURRENT_MAX_MA: MotorLimit(type=MotorLimitTypes.CURRENT_MAX_MA, value=500.0),
            MotorLimitTypes.TEMPERATURE_MAX_C: MotorLimit(type=MotorLimitTypes.TEMPERATURE_MAX_C, value=80.0),
        },
        variant=None,
        description="SCS0009 micro-servo",
        encoder_resolution=1024,
        position_scale=(2 * math.pi) / 1024,
        gear_ratio=1.0,
        brand=MotorBrand.FEETECH,
    ),
    # Legacy models for compatibility
    MotorModelInfo(
        model="SM8512BL",
        model_ids=[8512],  # Placeholder model_id
        limits={
            MotorLimitTypes.VOLTAGE_MIN: MotorLimit(type=MotorLimitTypes.VOLTAGE_MIN, value=4.8),
            MotorLimitTypes.VOLTAGE_MAX: MotorLimit(type=MotorLimitTypes.VOLTAGE_MAX, value=7.4),
            MotorLimitTypes.CURRENT_MAX_MA: MotorLimit(type=MotorLimitTypes.CURRENT_MAX_MA, value=1000.0),
            MotorLimitTypes.TEMPERATURE_MAX_C: MotorLimit(type=MotorLimitTypes.TEMPERATURE_MAX_C, value=80.0),
        },
        variant=None,
        description="SM8512BL servo motor (legacy)",
        encoder_resolution=4096,
        position_scale=(2 * math.pi) / 4096,
        gear_ratio=1.0,
        brand=MotorBrand.FEETECH,
    ),
    MotorModelInfo(
        model="ST3225",
        model_ids=[3225],  # Placeholder model_id
        limits={
            MotorLimitTypes.VOLTAGE_MIN: MotorLimit(type=MotorLimitTypes.VOLTAGE_MIN, value=4.8),
            MotorLimitTypes.VOLTAGE_MAX: MotorLimit(type=MotorLimitTypes.VOLTAGE_MAX, value=7.4),
            MotorLimitTypes.CURRENT_MAX_MA: MotorLimit(type=MotorLimitTypes.CURRENT_MAX_MA, value=1000.0),
            MotorLimitTypes.TEMPERATURE_MAX_C: MotorLimit(type=MotorLimitTypes.TEMPERATURE_MAX_C, value=80.0),
        },
        variant=None,
        description="ST3225 servo motor (legacy)",
        encoder_resolution=4096,
        position_scale=(2 * math.pi) / 4096,
        gear_ratio=1.0,
        brand=MotorBrand.FEETECH,
    ),
]

# Consolidated convenience list of all Feetech models across series
FEETECH_MODELS_LIST: list[MotorModelInfo] = SCS_STS_MODELS_LIST

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
