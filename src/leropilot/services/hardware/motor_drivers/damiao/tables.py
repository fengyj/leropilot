"""Damiao motor model tables and protocol constants.

Express Damiao models as typed `MotorModelInfo` entries to support
MotorService table-based lookups and to retire `motor_specs.json`.
"""

from __future__ import annotations

from leropilot.models.hardware import MotorBrand, MotorLimit, MotorLimitTypes, MotorModelInfo


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
    AVAILABLE_BAUDRATES = [500000, 1000000, 2000000, 5000000]  # CAN FD supported
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


DAMAIO_MODELS_LIST: list[MotorModelInfo] = [
    MotorModelInfo(
        model="DM4310",
        model_ids=[17168],  # 0x4310
        limits={
            MotorLimitTypes.VOLTAGE_MIN: MotorLimit(type=MotorLimitTypes.VOLTAGE_MIN, value=12.0),
            MotorLimitTypes.VOLTAGE_MAX: MotorLimit(type=MotorLimitTypes.VOLTAGE_MAX, value=30.0),
            MotorLimitTypes.CURRENT_MAX_MA: MotorLimit(type=MotorLimitTypes.CURRENT_MAX_MA, value=4000.0),
            MotorLimitTypes.TEMPERATURE_MAX_C: MotorLimit(type=MotorLimitTypes.TEMPERATURE_MAX_C, value=100.0),
        },
        variant="DM4310",
        description="Damiao DM4310 servo motor (base variant)",
        encoder_resolution=16384,  # 14-bit encoder
        brand=MotorBrand.DAMIAO,
    ),
    MotorModelInfo(
        model="DM4340",
        model_ids=[17216, 28672],  # 0x4340, 0x7000 (Integrated J-series)
        limits={
            MotorLimitTypes.VOLTAGE_MIN: MotorLimit(type=MotorLimitTypes.VOLTAGE_MIN, value=12.0),
            MotorLimitTypes.VOLTAGE_MAX: MotorLimit(type=MotorLimitTypes.VOLTAGE_MAX, value=30.0),
            MotorLimitTypes.CURRENT_MAX_MA: MotorLimit(type=MotorLimitTypes.CURRENT_MAX_MA, value=8000.0),
            MotorLimitTypes.TEMPERATURE_MAX_C: MotorLimit(type=MotorLimitTypes.TEMPERATURE_MAX_C, value=100.0),
            MotorLimitTypes.TORQUE_MAX_NM: MotorLimit(type=MotorLimitTypes.TORQUE_MAX_NM, value=28.0),
        },
        variant="DM4340P",
        description="Damiao DM4340P servo motor (P variant with cross-roller bearings)",
        encoder_resolution=16384,  # 14-bit encoder
        brand=MotorBrand.DAMIAO,
    ),
    MotorModelInfo(
        model="DM8009",
        model_ids=[32777],  # 0x8009
        limits={
            MotorLimitTypes.VOLTAGE_MIN: MotorLimit(type=MotorLimitTypes.VOLTAGE_MIN, value=24.0),
            MotorLimitTypes.VOLTAGE_MAX: MotorLimit(type=MotorLimitTypes.VOLTAGE_MAX, value=48.0),
            MotorLimitTypes.CURRENT_MAX_MA: MotorLimit(type=MotorLimitTypes.CURRENT_MAX_MA, value=9000.0),
            MotorLimitTypes.TEMPERATURE_MAX_C: MotorLimit(type=MotorLimitTypes.TEMPERATURE_MAX_C, value=100.0),
        },
        variant="DM8009",
        description="Damiao DM8009 servo motor (base variant)",
        encoder_resolution=16384,  # 14-bit encoder
        brand=MotorBrand.DAMIAO,
    ),
    MotorModelInfo(
        model="DM8009",
        model_ids=[32777],  # 0x8009
        limits={
            MotorLimitTypes.VOLTAGE_MIN: MotorLimit(type=MotorLimitTypes.VOLTAGE_MIN, value=24.0),
            MotorLimitTypes.VOLTAGE_MAX: MotorLimit(type=MotorLimitTypes.VOLTAGE_MAX, value=48.0),
            MotorLimitTypes.CURRENT_MAX_MA: MotorLimit(type=MotorLimitTypes.CURRENT_MAX_MA, value=9000.0),
            MotorLimitTypes.TEMPERATURE_MAX_C: MotorLimit(type=MotorLimitTypes.TEMPERATURE_MAX_C, value=100.0),
        },
        variant="DM8009P",
        description="Damiao DM8009P servo motor (P variant with cross-roller bearings)",
        encoder_resolution=16384,  # 14-bit encoder
        brand=MotorBrand.DAMIAO,
    ),
    MotorModelInfo(
        model="DM6006",
        model_ids=[24582],  # 0x6006
        limits={
            MotorLimitTypes.VOLTAGE_MIN: MotorLimit(type=MotorLimitTypes.VOLTAGE_MIN, value=24.0),
            MotorLimitTypes.VOLTAGE_MAX: MotorLimit(type=MotorLimitTypes.VOLTAGE_MAX, value=48.0),
            MotorLimitTypes.CURRENT_MAX_MA: MotorLimit(type=MotorLimitTypes.CURRENT_MAX_MA, value=6000.0),
            MotorLimitTypes.TEMPERATURE_MAX_C: MotorLimit(type=MotorLimitTypes.TEMPERATURE_MAX_C, value=100.0),
        },
        variant=None,
        description="Damiao DM6006 servo motor",
        encoder_resolution=16384,  # 14-bit encoder
        brand=MotorBrand.DAMIAO,
    ),
    MotorModelInfo(
        model="DM8006",
        model_ids=[32774],  # 0x8006
        limits={
            MotorLimitTypes.VOLTAGE_MIN: MotorLimit(type=MotorLimitTypes.VOLTAGE_MIN, value=24.0),
            MotorLimitTypes.VOLTAGE_MAX: MotorLimit(type=MotorLimitTypes.VOLTAGE_MAX, value=48.0),
            MotorLimitTypes.CURRENT_MAX_MA: MotorLimit(type=MotorLimitTypes.CURRENT_MAX_MA, value=8000.0),
            MotorLimitTypes.TEMPERATURE_MAX_C: MotorLimit(type=MotorLimitTypes.TEMPERATURE_MAX_C, value=100.0),
        },
        variant=None,
        description="Damiao DM8006 servo motor",
        encoder_resolution=16384,  # 14-bit encoder
        brand=MotorBrand.DAMIAO,
    ),
    MotorModelInfo(
        model="DM10054",
        model_ids=[41042],  # 0xA046
        limits={
            MotorLimitTypes.VOLTAGE_MIN: MotorLimit(type=MotorLimitTypes.VOLTAGE_MIN, value=24.0),
            MotorLimitTypes.VOLTAGE_MAX: MotorLimit(type=MotorLimitTypes.VOLTAGE_MAX, value=48.0),
            MotorLimitTypes.CURRENT_MAX_MA: MotorLimit(type=MotorLimitTypes.CURRENT_MAX_MA, value=54000.0),
            MotorLimitTypes.TEMPERATURE_MAX_C: MotorLimit(type=MotorLimitTypes.TEMPERATURE_MAX_C, value=100.0),
        },
        variant=None,
        description="Damiao DM10054 servo motor",
        encoder_resolution=16384,  # 14-bit encoder
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
