from leropilot.services.hardware.motors import MotorService


def test_get_model_info_by_model_id_damiao() -> None:
    svc = MotorService()
    info = svc.get_model_info_by_model_id("damiao", 17168)
    assert info is not None
    assert info.model == "DM4310"
