
from leropilot.models.hardware import MotorModelInfo
from leropilot.services.hardware.motor_drivers.dynamixel.drivers import DynamixelDriver


def test_identify_model_dynamixel(monkeypatch):
    drv = DynamixelDriver("/dev/null", 1000000)
    # Fake port and packet handler
    drv.port_handler = object()

    class FakePacketHandler:
        def ping(self, port_handler, motor_id):
            # return model_number, comm_result, error
            return (1190, 0, 0)

    fake_ph = FakePacketHandler()
    drv.packet_handler = fake_ph

    # Ensure COMM_SUCCESS constant is available and equals 0 for test purposes

    info = drv.identify_model(1)
    assert isinstance(info, MotorModelInfo)
    assert info.model.startswith("XL330") or info.model == "XL330"
