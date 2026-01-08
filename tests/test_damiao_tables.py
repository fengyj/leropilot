from leropilot.services.hardware.motor_drivers.damiao.tables import DAMAIO_MODELS_LIST, models_for_id, select_model_for_number
from leropilot.models.hardware import MotorBrand


def test_damiao_tables_populated():
    assert DAMAIO_MODELS_LIST
    m = select_model_for_number(17168)
    assert m is not None
    assert m.model == "DM4310"
    assert getattr(m, "brand", None) == MotorBrand.DAMIAO


def test_models_for_id():
    lst = models_for_id(24582)
    assert lst and lst[0].model == "DM6006"
    assert getattr(lst[0], "brand", None) == MotorBrand.DAMIAO