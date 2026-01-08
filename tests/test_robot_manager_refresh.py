# ruff: noqa: ANN201, ANN001
from unittest.mock import Mock
from leropilot.models.hardware import Robot, RobotDefinition, MotorBusDefinition, RobotMotorDefinition, RobotMotorBusConnection, DeviceStatus
from leropilot.models.hardware import MotorModelInfo, MotorBrand
from leropilot.services.hardware.robots import get_robot_manager


def _make_robot_with_definition():
    # Create a simple RobotDefinition with one motorbus named 'motorbus'
    motor_def = RobotMotorDefinition(name="1", id=1, brand="feetech", model="STS3215", variant=None)
    mb_def = MotorBusDefinition(type="FakeSerialBus", motors={"1": motor_def}, baud_rate=115200)
    rdef = RobotDefinition(id="", lerobot_name=None, display_name="Unknown", description="", motor_buses={"motorbus": mb_def})
    return rdef


class FakeSerialBus:
    def __init__(self, interface="COM3", baud=115200, motors=None):
        self.interface = interface
        self.baud_rate = baud
        self.motors = motors or {}


def test_refresh_status_available(monkeypatch):
    manager = get_robot_manager()
    manager._robots.clear()

    # Prepare robot
    rdef = _make_robot_with_definition()
    robot = Robot(id="r1", name="R1", definition=rdef, is_transient=False, motor_bus_connections={"motorbus": RobotMotorBusConnection(motor_bus_type="FakeSerialBus", interface="COM3", baudrate=115200, serial_number=None)})
    manager.add_robot(robot)

    # Fake discovered bus with matching motor and MotorModelInfo
    mi = MotorModelInfo(model="STS3215", model_ids=[1], limits={}, variant=None, brand=MotorBrand.FEETECH)
    bus = FakeSerialBus(motors={1: (Mock(), mi)})
    monkeypatch.setattr(manager, "_discover_motor_buses", lambda filters=None: [(bus, None, "Feetech")])

    managers = manager.refresh_status()
    assert isinstance(managers, list)
    r = manager.get_robot(robot.id)
    assert r.status == DeviceStatus.AVAILABLE


def test_refresh_status_offline_and_remove_transient(monkeypatch):
    manager = get_robot_manager()
    manager._robots.clear()

    rdef = _make_robot_with_definition()
    # Transient robot with no connection
    robot = Robot(id="t1", name="T1", definition=rdef, is_transient=True, motor_bus_connections={"motorbus": RobotMotorBusConnection(motor_bus_type="FakeSerialBus", interface="COMX", baudrate=115200, serial_number=None)})
    manager.add_robot(robot)

    # No discovered buses
    monkeypatch.setattr(manager, "_discover_motor_buses", lambda filters=None: [])

    res = manager.refresh_status(robot.id)
    # Robot was transient and offline so should be removed and return None
    assert res is None
    assert manager.get_robot("t1") is None


def test_refresh_status_invalid_on_mismatch(monkeypatch):
    manager = get_robot_manager()
    manager._robots.clear()

    rdef = _make_robot_with_definition()
    robot = Robot(id="r2", name="R2", definition=rdef, is_transient=False, motor_bus_connections={"motorbus": RobotMotorBusConnection(motor_bus_type="FakeSerialBus", interface="COM3", baudrate=115200, serial_number=None)})
    manager.add_robot(robot)

    # Discovered bus present but motor model differs
    mi = MotorModelInfo(model="OTHER", model_ids=[999], limits={}, variant=None, brand=MotorBrand.FEETECH)
    bus = FakeSerialBus(motors={1: (Mock(), mi)})
    monkeypatch.setattr(manager, "_discover_motor_buses", lambda filters=None: [(bus, None, "Feetech")])

    manager.refresh_status()
    r = manager.get_robot("r2")
    assert r.status == DeviceStatus.INVALID
