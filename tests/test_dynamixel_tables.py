from leropilot.services.hardware.motor_drivers.dynamixel.tables import (
    DYNAMIXEL_MODELS_LIST,
    models_for_id,
    select_model_for_number,
)


def test_dynamixel_tables_populated():
    assert DYNAMIXEL_MODELS_LIST
    # Known mapping: 1190 -> XL330 M077
    candidates = models_for_id(1190)
    assert candidates
    model = select_model_for_number(1190)
    assert model is not None
    assert model.model == "XL330"
    assert model.variant == "M077"
    from leropilot.models.hardware import MotorBrand

    assert getattr(model, "brand", None) == MotorBrand.DYNAMIXEL
