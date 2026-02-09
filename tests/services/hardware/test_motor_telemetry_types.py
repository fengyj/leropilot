import pytest

from leropilot.models.hardware import MotorTelemetry, PositionType


def test_motor_telemetry_coerces_numeric_types():
    # Provide ints for fields that should be floats; model should coerce
    mt = MotorTelemetry(
        id=1,
        position=1024.0,
        position_type=PositionType.RAW,
        velocity=12,
        current=150,
        load=50,
        temperature=36,
        voltage=7,
        moving=False,
        error=0,
    )

    assert isinstance(mt.current, float)
    assert mt.current == 150.0
    assert isinstance(mt.temperature, float)
    assert mt.temperature == 36.0
    assert isinstance(mt.voltage, float)
    assert mt.voltage == 7.0
    assert isinstance(mt.load, int)
    assert 0 <= mt.load <= 100


def test_motor_telemetry_invalid_current_raises():
    with pytest.raises(ValueError):
        MotorTelemetry(
            id=1,
            position=0.0,
            position_type=PositionType.RAW,
            velocity=0.0,
            current="not-a-number",
            load=0,
            temperature=0.0,
            voltage=0.0,
            moving=False,
            error=0,
        )
