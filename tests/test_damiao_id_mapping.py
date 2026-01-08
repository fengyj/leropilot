from types import SimpleNamespace

from leropilot.services.hardware.motor_drivers.damiao.drivers import DamiaoCAN_Driver


class FakeMsg(SimpleNamespace):
    pass


def test_ping_with_recv_mapping(monkeypatch):
    # Setup driver with mapping: logical ID 3 -> recv ID 0x13
    driver = DamiaoCAN_Driver("PCAN_USBBUS1", 1000000)

    # Stub send to always succeed
    monkeypatch.setattr(driver, "_send_can_frame", lambda motor_id, data: True)

    # Create a fake message that comes from recv_id and includes payload
    fake_msg = FakeMsg(arbitration_id=0x13, data=bytes([3, 0, 0, 0, 0, 0, 0, 0]))

    # Patch _recv_motor_response to return our fake_msg when expected is (3,0x13)
    monkeypatch.setattr(driver, "_recv_motor_response", lambda expected_id, timeout=0.1: fake_msg if expected_id == (3, 0x13) else None)

    assert driver.ping_motor((3, 0x13)) is True
