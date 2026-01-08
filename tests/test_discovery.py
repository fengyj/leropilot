# ruff: noqa: ANN201, ANN001, ANN204
from fastapi.testclient import TestClient

from leropilot.main import app
from leropilot.services.hardware.robots import get_robot_manager
from leropilot.services.hardware.robots import RobotsDiscoveryService
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
    ports = [
        {"port": "COM3", "description": "FTDI USB Serial", "serial_number": "SN123", "vid": "0403", "pid": "6001"},
        {"port": "COM4", "description": "CH340 USB Serial", "serial_number": None, "vid": "1a86", "pid": "7523"},
    ]
    dummy = DummyAdapter(ports)

    # Monkeypatch PlatformAdapter used inside RobotsDiscoveryService
    monkeypatch.setattr(
        RobotsDiscoveryService,
        "__init__",
        lambda self: setattr(self, "adapter", dummy) or setattr(self, "adapter", dummy),
    )

    # Ensure manager has robot with serial SN123 already added
    manager = get_robot_manager()
    # Clear existing robots for test isolation
    manager._robots.clear()

    # Add robot with serial SN123
    manager.add_robot(Robot(id="SN123", name="Existing Robot", status=DeviceStatus.AVAILABLE))

    # Call discovery endpoint
    resp = client.get("/api/hardware/discovery")
    assert resp.status_code == 200
    data = resp.json()

    # Should not include SN123 (already added)
    robots = data.get("robots", [])
    assert all(r.get("serial_number") != "SN123" for r in robots)

    # Should include the device without serial and mark it unsupported
    assert any(
        r.get("serial_number") is None
        and r.get("supported") is False
        and r.get("unsupported_reason") == "missing_serial_number"
        for r in robots
    )
