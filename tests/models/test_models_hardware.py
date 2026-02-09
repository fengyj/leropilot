import pytest

from leropilot.models.hardware import (
    MotorBrand,
    MotorLimit,
    MotorModelInfo,
)


def test_motor_model_info_limits():
    limit_v = MotorLimit(type=MotorLimit.LIMIT_VOLTAGE_MIN, value=6.0)
    limit_c = MotorLimit(type=MotorLimit.LIMIT_CURRENT_MAX_MA, value=2000.0)

    model = MotorModelInfo(
        model="STS3215",
        model_ids=[3215, 1545],
        limits={limit_v.type: limit_v, limit_c.type: limit_c},
        variant=None,
        description="Test motor",
        encoder_resolution=4096,
        position_scale=2.0,
        encoding="twos_complement",
        endianness="little",
        gear_ratio=1.0,
        direction_inverted=False,
        baudrates=[115200, 57600],
        brand=MotorBrand.FEETECH,
    )

    assert model.model == "STS3215"
    assert MotorLimit.LIMIT_VOLTAGE_MIN in model.limits
    assert model.limits[MotorLimit.LIMIT_VOLTAGE_MIN].value == 6.0
    assert model.encoder_resolution == 4096


def test_constants_and_exception() -> None:
    assert MotorLimit.LIMIT_VOLTAGE_MIN
    assert MotorLimit.LIMIT_CURRENT_MAX_MA
    # Basic ValueError sanity check (used for ambiguity in drivers)
    try:
        raise ValueError("ambiguous")
    except ValueError as e:
        assert str(e) == "ambiguous"


def test_motor_model_info_requires_brand() -> None:
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        # brand is required (provide encoder_resolution so brand remains the failing field)
        MotorModelInfo(model="X", model_ids=[0], limits={}, encoder_resolution=4096.0)
