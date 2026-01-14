from leropilot.services.hardware.motors import MotorService


def test_get_model_info_by_model_id_dynamixel() -> None:
    svc = MotorService()
    info = svc.get_model_info_by_model_id("dynamixel", 1190)
    assert info is not None
    assert info.model == "XL330"
    assert info.variant == "M077"
