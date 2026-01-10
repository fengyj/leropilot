# ruff: noqa: ANN201, ANN001, ANN204
from fastapi.testclient import TestClient

from leropilot.main import app
from leropilot.services.hardware.robots import get_robot_manager
from leropilot.models.hardware import Robot, DeviceStatus

client = TestClient(app)

class DummyAdapter:
    def __init__(self, ports):
        self._ports = ports
        self.platform = "test"
    def discover_serial_ports(self):
        return self._ports
    def discover_can_interfaces(self):
        return []


def test_discovery_filters_added_and_marks_missing_serial(monkeypatch, tmp_path):
    # Prepare dummy serial ports: one with serial, one without
    from types import SimpleNamespace
    ports = [
        SimpleNamespace(port="COM3", description="FTDI USB Serial", serial_number="SN123", vid="0403", pid="6001", manufacturer="FTDI"),
        SimpleNamespace(port="COM4", description="CH340 USB Serial", serial_number=None, vid="1a86", pid="7523", manufacturer="CH340"),
    ]
    dummy = DummyAdapter(ports)

    # Instead of probing real devices, monkeypatch RobotManager._discover_motor_buses to return deterministic results
    manager = get_robot_manager()
    manager._robots.clear()

    # Construct two fake buses: one with serial SN123, another without serial
    class FakeBus:
        def __init__(self, interface, motors, baud_rate=115200):
            self.interface = interface
            self.baud_rate = baud_rate
            self.motors = motors

    from unittest.mock import Mock
    from leropilot.models.hardware import MotorModelInfo, MotorBrand

    mi = MotorModelInfo(model="DM4310", model_ids=[17168], limits={}, variant=None, brand=MotorBrand.DAMIAO)
    bus_with_serial = FakeBus("COM3", {1: (Mock(), mi)})
    bus_no_serial = FakeBus("COM4", {1: (Mock(), mi)})

    monkeypatch.setattr(manager, "_discover_motor_buses", lambda filters=None: [(bus_with_serial, "SN123", "FTDI"), (bus_no_serial, None, "CH340")])

    # Add robot with serial SN123; monkeypatch verification to avoid hardware probing
    monkeypatch.setattr(manager, "verify_robot", lambda self: True)
    manager.add_robot(Robot(id="SN123", name="Existing Robot", status=DeviceStatus.AVAILABLE))

    # Call discovery endpoint
    resp = client.get("/api/hardware/robots/discovery")
    assert resp.status_code == 200
    robots = resp.json()

    # Should not include SN123 (already added)
    assert all(r.get("serial_number") != "SN123" for r in robots)

    # Should include the device without serial and mark it transient (no serial)
    assert any(
        r.get("serial_number") is None
        and r.get("is_transient") is True
        and r.get("motor_bus_connections") and r.get("motor_bus_connections").get("motorbus", {}).get("serial_number") is None
        for r in robots
    )
