from leropilot.models.hardware import MotorProtectionParams
from leropilot.services.hardware.motors import MotorService


def test_get_spec_by_model_id_dynamixel() -> None:
    svc = MotorService()
    res = svc.get_spec_by_model_id("dynamixel", 1190)
    assert res is not None
    model_name, params = res
    assert isinstance(params, MotorProtectionParams)
    assert model_name.startswith("XL330")
    # Check converted limits
    assert params.voltage_min == 3.7
    assert params.current_max == 400
