# ruff: noqa
from fastapi.testclient import TestClient

import leropilot.services.hardware.motors as motor_svc_mod
from leropilot.main import app
from leropilot.models.hardware import MotorTelemetry, ProtectionStatus
from leropilot.services.hardware.manager import get_hardware_manager

client = TestClient(app)


class FakeDriver:
    def __init__(self):
        self.torque_calls = []
        self.connected = True

    def write_torque_enable(self, motor_id, enabled):
        self.torque_calls.append((motor_id, enabled))

    def disconnect(self):
        self.connected = False


def test_auto_disable_torque_on_critical(monkeypatch):
    manager = get_hardware_manager()
    manager._devices.clear()
    manager.add_device(device_id="SNPROT", category="robot", name="ProtRobot")

    fake_driver = FakeDriver()

    # Patch driver creation to return fake driver
    monkeypatch.setattr(motor_svc_mod.MotorService, "create_driver", lambda self, interface, brand, interface_type, baud_rate: fake_driver)

    # Patch read_telemetry_with_protection to return a MotorTelemetry with critical protection on first call
    call_count = {"n": 0}

    def fake_read(self, driver, motor_id, brand, model, overrides=None):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return MotorTelemetry(
                id=motor_id,
                position=0.0,
                velocity=0.0,
                current=0,
                load=0,
                temperature=100,
                voltage=12.0,
                moving=False,
                goal_position=0.0,
                error=0,
                protection_status=ProtectionStatus(status="critical", violations=[]),
            )
        # Subsequent calls return ok
        return MotorTelemetry(
            id=motor_id,
            position=0.0,
            velocity=0.0,
            current=0,
            load=0,
            temperature=30,
            voltage=12.0,
            moving=False,
            goal_position=0.0,
            error=0,
            protection_status=ProtectionStatus(status="ok", violations=[]),
        )

    monkeypatch.setattr(motor_svc_mod.MotorService, "read_telemetry_with_protection", fake_read)

    ws_path = "/api/ws/hardware/robots/SNPROT?interface=COM3&baud_rate=1000000"
    with client.websocket_connect(ws_path) as ws:
        # Start telemetry
        ws.send_json({"type": "start_telemetry", "interval_ms": 10})

        # Allow some time for telemetry task to run
        import time as _time

        _time.sleep(0.5)

        # Ensure driver had torque disabled for motor 1 (default discovered range)
        assert (1, False) in fake_driver.torque_calls
