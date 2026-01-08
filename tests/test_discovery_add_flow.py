# ruff: noqa: ANN201, ANN001, ANN204
from fastapi.testclient import TestClient

from leropilot.main import app
from leropilot.services.hardware.robots import get_robot_manager
from leropilot.services.hardware.robots import RobotsDiscoveryService
from leropilot.models.hardware import Robot

client = TestClient(app)


class DummyAdapter:
    def __init__(self, ports):
        self._ports = ports
        self.platform = "test"

    def discover_serial_ports(self):
        return self._ports

    def discover_can_interfaces(self):
        return []


def test_discovery_then_add_device(monkeypatch, tmp_path):
    # Prepare a port with a valid serial
    ports = [
        {"port": "COM3", "description": "FTDI USB Serial", "serial_number": "SN_ADD_1", "vid": "0403", "pid": "6001"}
    ]

    dummy = DummyAdapter(ports)

    # Monkeypatch PlatformAdapter used inside RobotsDiscoveryService
    monkeypatch.setattr(
        RobotsDiscoveryService,
        "__init__",
        lambda self: setattr(self, "adapter", dummy) or setattr(self, "adapter", dummy),
    )

    manager = get_robot_manager()
    manager._robots.clear()

    # Discovery should show the serial
    resp = client.get("/api/hardware/discovery")
    assert resp.status_code == 200
    data = resp.json()
    robots = data.get("robots", [])
    assert any(r.get("serial_number") == "SN_ADD_1" for r in robots)

    # Add device using the serial from discovery
    payload = {"id": "SN_ADD_1", "name": "Added Robot"}
    add_resp = client.post("/api/hardware/robots", json=payload)
    # Adding without explicit motor_bus_connections is disallowed
    assert add_resp.status_code == 409

    # Device should not have been added and discovery still includes the serial
    resp2 = client.get("/api/hardware/discovery")
    data2 = resp2.json()
    robots2 = data2.get("robots", [])
    assert any(r.get("serial_number") == "SN_ADD_1" for r in robots2)

    # Manager should not have the device
    device = manager.get_robot("SN_ADD_1")
    assert device is None
