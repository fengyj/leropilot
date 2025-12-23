# ruff: noqa: ANN201, ANN001, ANN204
from fastapi.testclient import TestClient

from leropilot.main import app
from leropilot.services.hardware.manager import get_hardware_manager
from leropilot.services.hardware.robots import RobotsDiscoveryService

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

    manager = get_hardware_manager()
    manager._devices.clear()

    # Discovery should show the serial
    resp = client.get("/api/hardware/discovery")
    assert resp.status_code == 200
    data = resp.json()
    robots = data.get("robots", [])
    assert any(r.get("serial_number") == "SN_ADD_1" for r in robots)

    # Add device using the serial from discovery
    payload = {"id": "SN_ADD_1", "category": "robot", "name": "Added Robot"}
    add_resp = client.post("/api/hardware/devices", json=payload)
    assert add_resp.status_code == 200

    # Subsequent discovery should not include that serial
    resp2 = client.get("/api/hardware/discovery")
    data2 = resp2.json()
    robots2 = data2.get("robots", [])
    assert all(r.get("serial_number") != "SN_ADD_1" for r in robots2)

    # Manager has the device
    device = manager.get_device("SN_ADD_1")
    assert device is not None
    assert device.name == "Added Robot"
