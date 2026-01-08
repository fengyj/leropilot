"""Tests for Damiao scan behavior regarding recv-id mapping and skipping recv addresses."""

from unittest.mock import Mock, patch

from leropilot.services.hardware.motor_drivers.damiao.drivers import DamiaoCAN_Driver


def test_scan_detects_recv_and_skips_subsequent_recv():
    driver = DamiaoCAN_Driver("pcan:PCAN_USBBUS1")
    calls: list[int] = []

    def fake_send(self, motor_id, data):
        s = int(motor_id[0]) if isinstance(motor_id, (list, tuple)) else int(motor_id)
        self._last_sent = s
        calls.append(s)
        return True

    def fake_recv(self, expected_id=None, timeout=0.05):
        s = getattr(self, "_last_sent", None)
        if s == 1:
            # Reply from recv id 0x13 with payload indicating source 1
            resp = Mock()
            resp.arbitration_id = 0x13
            resp.data = bytes([1, 0, 0, 0, 0, 0, 0, 0])
            return resp
        elif s == 0x13:
            # If we accidentally sent to recv id, return a payload that points to source 1
            resp = Mock()
            resp.arbitration_id = 0x13
            resp.data = bytes([1, 0, 0, 0, 0, 0, 0, 0])
            return resp
        return None

    with patch.object(DamiaoCAN_Driver, "_send_can_frame", new=fake_send), patch.object(
        DamiaoCAN_Driver, "_recv_motor_response", new=fake_recv
    ):
        discovered = driver.scan_motors(scan_range=[1, 0x13, 2])

    # We should discover one motor (send=1 with recv=0x13)
    assert len(discovered) == 1
    rid = next(iter(discovered.keys()))
    assert rid[0] == 1
    assert rid[1] == 0x13

    # Ensure we did not attempt to send frames to the recv id (0x13) after discovery
    assert 0x13 not in calls


def test_scan_handles_recv_id_sent_first_and_maps_correctly():
    # If the scanner attempts the recv id first, it should detect it's a recv id
    # (payload points to another send) and skip it, later discovering the correct send.
    driver = DamiaoCAN_Driver("pcan:PCAN_USBBUS1")
    calls: list[int] = []

    def fake_send(self, motor_id, data):
        s = int(motor_id[0]) if isinstance(motor_id, (list, tuple)) else int(motor_id)
        self._last_sent = s
        calls.append(s)
        return True

    def fake_recv(self, expected_id=None, timeout=0.05):
        s = getattr(self, "_last_sent", None)
        if s == 0x13:
            # Probing 0x13 returns a frame whose payload indicates source=1
            resp = Mock()
            resp.arbitration_id = 0x13
            resp.data = bytes([1, 0, 0, 0, 0, 0, 0, 0])
            return resp
        if s == 1:
            resp = Mock()
            resp.arbitration_id = 0x13
            resp.data = bytes([1, 0, 0, 0, 0, 0, 0, 0])
            return resp
        return None

    with patch.object(DamiaoCAN_Driver, "_send_can_frame", new=fake_send), patch.object(
        DamiaoCAN_Driver, "_recv_motor_response", new=fake_recv
    ):
        discovered = driver.scan_motors(scan_range=[0x13, 1])

    assert len(discovered) == 1
    rid = next(iter(discovered.keys()))
    assert rid[0] == 1
    assert rid[1] == 0x13
    # We did send to 0x13 once (the probe), but it should not be returned as a motor
    assert 0x13 in calls and 1 in calls


if __name__ == "__main__":
    import pytest

    pytest.main([__file__, "-q"])