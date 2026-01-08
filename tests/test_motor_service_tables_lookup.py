from leropilot.services.hardware.motors import MotorService
from leropilot.models.hardware import MotorProtectionParams


def test_get_model_info_by_model_id_feetech():
    svc = MotorService()
    info = svc.get_model_info_by_model_id("feetech", 3215)
    assert info is not None
    # model id 3215 corresponds to the STS3215 base model (no variant) in tables
    assert info.model == "STS3215"


def test_get_spec_by_model_id_uses_tables(monkeypatch):
    svc = MotorService()
    res = svc.get_spec_by_model_id("feetech", 3215)
    assert res is not None
    model_name, params = res
    assert isinstance(params, MotorProtectionParams)
    assert model_name.startswith("STS3215")
    assert params.voltage_min == 6.0
    assert params.current_max == 150
