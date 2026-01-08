from leropilot.services.hardware.motors import MotorService
from leropilot.models.hardware import MotorProtectionParams


def test_get_spec_by_model_id_dynamixel():
    svc = MotorService()
    res = svc.get_spec_by_model_id("dynamixel", 1190)
    assert res is not None
    model_name, params = res
    assert isinstance(params, MotorProtectionParams)
    assert model_name.startswith("XL330")
    # Check converted limits
    assert params.voltage_min == 3.7
    assert params.current_max == 400
