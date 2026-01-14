import pytest

# ruff: noqa: ANN201, ANN001
from unittest.mock import Mock

from leropilot.models.hardware import MotorBrand, MotorModelInfo, RobotMotorDefinition
from leropilot.services.hardware.robots import get_robot_manager


def test_get_pending_devices_with_serial_number(monkeypatch: pytest.MonkeyPatch) -> None:
    manager = get_robot_manager()
    # Ensure isolation
    manager._robots.clear()

    # Fake serial motor bus with two motors of same variant
    class FakeSerialBus:
        def __init__(self) -> None:
            self.interface = "COM3"
            self.baud_rate = 115200
            self.motors = {}

    bus = FakeSerialBus()
    mi1 = MotorModelInfo(model="STS3215", model_ids=[1], limits={}, variant="STS3215-C001", brand=MotorBrand.FEETECH)
    mi2 = MotorModelInfo(model="STS3215", model_ids=[1], limits={}, variant="STS3215-C001", brand=MotorBrand.FEETECH)

    bus.motors = {
        1: (Mock(), mi1),
        2: (Mock(), mi2),
    }

    def fake_discover_one(filters=None):
        return [(bus, "SN123", "Feetech")]

    monkeypatch.setattr(manager._discovery_service, "discover_motor_buses", fake_discover_one)

    pending = manager.get_pending_devices()
    assert len(pending) == 1
    r = pending[0]
    # Robot id should be a generated uuid (not the serial); serial lives on the connection
    assert r.id != "SN123"
    assert r.id != ""
    assert r.name == f"Unknown device on {bus.interface}"
    # DeviceStatus is emitted as its value due to pydantic settings
    assert r.status == "available"
    assert r.is_transient is False

    # MotorBus connection should carry serial_number
    conn = r.motor_bus_connections.get("motorbus")
    assert conn is not None
    assert conn.serial_number == "SN123"

    # Definition checks
    assert r.definition.display_name == r.name
    assert "STS3215-C001" in r.definition.description

    mb = r.definition.motor_buses.get("motorbus")
    assert mb is not None
    # motors is a list of RobotMotorDefinition
    assert len(mb.motors) == 2
    # Check first motor definition
    m0 = mb.motors[0]
    assert isinstance(m0, RobotMotorDefinition)
    assert m0.name == "1"
    assert m0.id == 1
    assert m0.model == "STS3215"
    assert m0.variant == "STS3215-C001"
    assert m0.need_calibration is True


def test_get_pending_devices_without_serial_number(monkeypatch: pytest.MonkeyPatch) -> None:
    manager = get_robot_manager()
    manager._robots.clear()

    class FakeCanBus:
        def __init__(self) -> None:
            self.interface = "can0"
            self.baud_rate = 1000000
            self.motors = {}

    bus = FakeCanBus()

    mi = MotorModelInfo(model="DM4310", model_ids=[17168], limits={}, variant=None, brand=MotorBrand.DAMIAO)
    bus.motors = {
        (3, 0x13): (Mock(), mi),
    }

    def fake_discover_none(filters=None):
        return [(bus, None, "Native")]

    monkeypatch.setattr(manager._discovery_service, "discover_motor_buses", fake_discover_none)

    pending = manager.get_pending_devices()
    assert len(pending) == 1
    r = pending[0]
    # Robot id is a generated uuid even when serial is missing
    assert r.id != ""
    assert r.is_transient is True
    assert r.name == f"Unknown device on {bus.interface}"
    # Description format may vary by locale; ensure it includes the model and count
    assert "DM4310" in r.definition.description and "1" in r.definition.description

    # Connection should exist but have no serial_number
    conn = r.motor_bus_connections.get("motorbus")
    assert conn is not None
    assert conn.serial_number is None

    mb = r.definition.motor_buses.get("motorbus")
    assert mb is not None
    assert len(mb.motors) == 1
    m0 = mb.motors[0]
    assert m0.name == "1"
    # RobotMotorDefinition coerces tuple id to first element
    assert m0.id == 3
    assert m0.model == "DM4310"
    assert m0.variant is None
    assert m0.brand.lower() == "damiao"
