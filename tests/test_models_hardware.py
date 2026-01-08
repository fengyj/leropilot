from leropilot.models.hardware import (
    MotorLimit,
    MotorModelInfo,
    AmbiguousModelError,
    LIMIT_VOLTAGE_MIN,
    LIMIT_CURRENT_MAX_MA,
    MotorBrand,
)


def test_motor_model_info_limits():
    limit_v = MotorLimit(type=LIMIT_VOLTAGE_MIN, value=6.0)
    limit_c = MotorLimit(type=LIMIT_CURRENT_MAX_MA, value=2000.0)

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
        operating_modes=["position", "velocity"],
        brand=MotorBrand.FEETECH,
    )

    assert model.model == "STS3215"
    assert LIMIT_VOLTAGE_MIN in model.limits
    assert model.limits[LIMIT_VOLTAGE_MIN].value == 6.0
    assert model.encoder_resolution == 4096
    assert "position" in model.operating_modes


def test_constants_and_exception():
    assert LIMIT_VOLTAGE_MIN
    assert LIMIT_CURRENT_MAX_MA
    # AmbiguousModelError exists and is an Exception
    try:
        raise AmbiguousModelError("ambiguous")
    except AmbiguousModelError as e:
        assert str(e) == "ambiguous"


def test_motor_model_info_requires_brand():
    import pytest

    with pytest.raises(Exception):
        # brand is required
        MotorModelInfo(model="X", model_ids=[0], limits={})
