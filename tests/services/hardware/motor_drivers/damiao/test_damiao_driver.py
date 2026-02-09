"""Tests for Damiao driver homing behaviour."""

from unittest.mock import Mock

from leropilot.exceptions import OperationalError
from leropilot.models.hardware import MotorModelInfo
from leropilot.services.hardware.motor_drivers.damiao.drivers import DamiaoCAN_Driver, DamiaoConstants


def test_damiao_supports_homing_offset_true():
    driver = DamiaoCAN_Driver("socketcan:can0")
    mi = MotorModelInfo(model="DM4310", model_ids=[17168], limits={}, brand="damiao", encoder_resolution=65536.0)
    assert driver.supports_homing_offset((1, 1), mi) is True


def test_write_homing_offset_sends_set_zero():
    driver = DamiaoCAN_Driver("socketcan:can0")
    # Patch _send_can_frame to assert it is called with SET_ZERO
    called = {}

    def fake_send(motor_id, data):
        called["motor_id"] = motor_id
        called["data"] = data
        return True

    driver._send_can_frame = fake_send
    # Mark driver as connected and provide a dummy bus so _ensure_connected passes
    driver.bus = Mock()
    driver.connected = True
    # Call write_homing_offset (offset is ignored)
    res = driver.write_homing_offset((3, 19), mi=None)
    assert res is True
    assert called["motor_id"] == (3, 19)
    # Check 3 low/high and command byte
    assert called["data"][0] == (3 & 0xFF)
    assert called["data"][1] == ((3 >> 8) & 0xFF)
    assert called["data"][2] == DamiaoConstants.CMD_SET_ZERO


def test_write_homing_offset_propagates_send_failure():
    driver = DamiaoCAN_Driver("socketcan:can0")

    def bad_send(motor_id, data):
        raise OperationalError(i18n_key="hardware.motor_device.send_failed", retriable=True)

    driver._send_can_frame = bad_send
    driver.bus = Mock()
    driver.connected = True
    try:
        driver.write_homing_offset((1, 2), mi=None)
        assert False, "Expected OperationalError"
    except OperationalError as e:
        assert (
            e.i18n_key == "hardware.motor_device.operation_failed" or e.i18n_key == "hardware.motor_device.send_failed"
        )


def test_send_mit_control_requires_all_parameters():
    driver = DamiaoCAN_Driver("socketcan:can0")
    # Calling without required args should raise TypeError
    try:
        driver.send_mit_control((1, 1))
        assert False, "Expected TypeError for missing parameters"
    except TypeError:
        pass


def test_send_mit_control_sends_frame_with_values():
    driver = DamiaoCAN_Driver("socketcan:can0")
    sent = {}

    def fake_send(send_id, data):
        sent['id'] = send_id
        sent['data'] = data
        return True

    driver.send_can_frame = fake_send
    result = driver.send_mit_control((3, 4), position=1.234, velocity=0.5, torque=0.1, kp=40.0, kd=2.0)
    assert result is True
    assert sent['id'] == 3
    assert isinstance(sent['data'], (bytes, bytearray))
    assert len(sent['data']) == 8
