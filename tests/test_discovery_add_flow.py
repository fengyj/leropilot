# ruff: noqa: ANN201, ANN001, ANN204
from fastapi.testclient import TestClient

from leropilot.main import app
from leropilot.services.hardware.robots import get_robot_manager
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
    from types import SimpleNamespace
    ports = [
        SimpleNamespace(port="COM3", description="FTDI USB Serial", serial_number="SN_ADD_1", vid="0403", pid="6001", manufacturer="FTDI"),
    ]

    dummy = DummyAdapter(ports)

    # Monkeypatch RobotManager._discover_motor_buses to return a deterministic bus with the serial
    manager = get_robot_manager()
    manager._robots.clear()

    class FakeBus:
        def __init__(self, interface, motors, baud_rate=115200):
            self.interface = interface
            self.baud_rate = baud_rate
            self.motors = motors

    from unittest.mock import Mock
    from leropilot.models.hardware import MotorModelInfo, MotorBrand

    mi = MotorModelInfo(model="STS3215", model_ids=[1], limits={}, variant="STS3215-C001", brand=MotorBrand.FEETECH)
    bus = FakeBus("COM3", {1: (Mock(), mi)})
    monkeypatch.setattr(manager, "_discover_motor_buses", lambda filters=None: [(bus, "SN_ADD_1", "FTDI")])

    # Discovery should show the serial
    resp = client.get("/api/hardware/robots/discovery")
    assert resp.status_code == 200
    robots = resp.json()
    assert any(r.get("motor_bus_connections", {}).get("motorbus", {}).get("serial_number") == "SN_ADD_1" for r in robots)

    # Add device using the serial from discovery
    payload = {"id": "SN_ADD_1", "name": "Added Robot"}
    add_resp = client.post("/api/hardware/robots", json=payload)
    # Adding without explicit motor_bus_connections is disallowed
    assert add_resp.status_code == 409

    # Device should not have been added and discovery still includes the serial
    resp2 = client.get("/api/hardware/robots/discovery")
    robots2 = resp2.json()
    assert any(r.get("motor_bus_connections", {}).get("motorbus", {}).get("serial_number") == "SN_ADD_1" for r in robots2)

    # Manager should not have the device
    device = manager.get_robot("SN_ADD_1")
    assert device is None
