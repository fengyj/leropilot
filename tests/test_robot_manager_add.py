# ruff: noqa: ANN201, ANN001, ANN204
from leropilot.services.hardware.robots import RobotManager
from leropilot.models.hardware import RobotVerificationError, Robot, DeviceStatus, RobotMotorBusConnection


def test_add_robot_uses_pending_connection_and_calls_verify(monkeypatch):
    manager = RobotManager()
    # isolate
    manager._robots.clear()

    # Create a pending robot with a motorbus that has serial_number 'SNX'
    pending = Robot(
        id="pending-1",
        name="Pending",
        status=DeviceStatus.AVAILABLE,
        motor_bus_connections={
            "motorbus": RobotMotorBusConnection(motor_bus_type="MockBus", interface="COM1", baudrate=115200, serial_number="SNX")
        },
        definition=None,
    )

    monkeypatch.setattr(manager, "get_pending_devices", lambda: [pending])

    called = {"verify": False}

    def fake_verify(rbt: Robot) -> bool:
        # Ensure motor_bus_connections were copied before verify is called
        assert rbt.motor_bus_connections is not None
        assert rbt.motor_bus_connections["motorbus"].serial_number == "SNX"
        called["verify"] = True
        return True

    monkeypatch.setattr(manager, "verify_robot", fake_verify)

    new = Robot(id="SNX", name="NewRobot", status=DeviceStatus.AVAILABLE)
    added = manager.add_robot(new)

    assert called["verify"] is True
    assert manager.get_robot("SNX") is not None


def test_add_robot_without_connections_skips_verify(monkeypatch):
    manager = RobotManager()
    manager._robots.clear()

    # Ensure verify_robot is NOT called
    def bad_verify(_):
        raise AssertionError("verify_robot should not be called when no connection available")

    monkeypatch.setattr(manager, "verify_robot", bad_verify)

    r = Robot(id="NOSERIAL", name="NoConn", status=DeviceStatus.AVAILABLE)
    added = manager.add_robot(r)

    assert manager.get_robot("NOSERIAL") is not None
