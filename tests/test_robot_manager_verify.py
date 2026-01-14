# ruff: noqa: ANN201, ANN001
from unittest.mock import Mock

from leropilot.models.hardware import MotorBrand, MotorBusDefinition, MotorModelInfo, RobotMotorDefinition
from leropilot.services.hardware.robots.verification import RobotVerificationService


def test_motor_bus_verify_matches_exact():
    manager = get_robot_manager()
    verifier = RobotVerificationService()

    class FakeBus:
        def __init__(self):
            self.interface = "COM3"
            self.baud_rate = 115200
            self.motors = {}

    bus = FakeBus()
    mi1 = MotorModelInfo(model="STS3215", model_ids=[1], limits={}, variant="STS3215-C001", brand=MotorBrand.FEETECH)
    mi2 = MotorModelInfo(model="STS3215", model_ids=[1], limits={}, variant="STS3215-C001", brand=MotorBrand.FEETECH)
    bus.motors = {1: (Mock(), mi1), 2: (Mock(), mi2)}

    mb_def = MotorBusDefinition(type=bus.__class__.__name__, motors={
        "1": RobotMotorDefinition(name="1", id=1, brand="feetech", model="STS3215", variant="STS3215-C001"),
        "2": RobotMotorDefinition(name="2", id=2, brand="feetech", model="STS3215", variant="STS3215-C001"),
    }, baud_rate=115200)

    assert verifier.verify_motor_bus(bus, mb_def) is True


def test_motor_bus_verify_tuple_key_and_variant_optional():
    manager = get_robot_manager()

    class FakeCanBus:
        def __init__(self):
            self.interface = "can0"
            self.baud_rate = 1000000
            self.motors = {}

    bus = FakeCanBus()
    mi = MotorModelInfo(model="DM4310", model_ids=[17168], limits={}, variant=None, brand=MotorBrand.DAMIAO)
    bus.motors = {(3, 0x13): (Mock(), mi)}

    mb_def = MotorBusDefinition(type=bus.__class__.__name__, motors={
        "1": RobotMotorDefinition(name="1", id=3, brand="damiao", model="DM4310", variant=None),
    }, baud_rate=1000000)

    # Strict exact-key matching: int id != tuple id => should be False
    assert manager._motor_bus_verify(bus, mb_def) is False


def test_motor_bus_verify_mismatch_brand_returns_false():
    manager = get_robot_manager()

    class FakeBus:
        def __init__(self):
            self.interface = "COM4"
            self.baud_rate = 115200
            self.motors = {}

    bus = FakeBus()
    mi = MotorModelInfo(model="STS3215", model_ids=[1], limits={}, variant="A", brand=MotorBrand.FEETECH)
    bus.motors = {1: (Mock(), mi)}

    mb_def = MotorBusDefinition(type=bus.__class__.__name__, motors={
        "1": RobotMotorDefinition(name="1", id=1, brand="dynamixel", model="STS3215", variant="A"),
    }, baud_rate=115200)

    assert manager._motor_bus_verify(bus, mb_def) is False


def test_motor_bus_verify_count_mismatch_returns_false():
    manager = get_robot_manager()

    class FakeBus:
        def __init__(self):
            self.interface = "COM5"
            self.baud_rate = 9600
            self.motors = {}

    bus = FakeBus()
    mi = MotorModelInfo(model="X", model_ids=[0], limits={}, variant=None, brand=MotorBrand.FEETECH)
    bus.motors = {1: (Mock(), mi)}

    mb_def = MotorBusDefinition(type=bus.__class__.__name__, motors={
        "1": RobotMotorDefinition(name="1", id=1, brand="feetech", model="X", variant=None),
        "2": RobotMotorDefinition(name="2", id=2, brand="feetech", model="X", variant=None),
    }, baud_rate=9600)

    assert manager._motor_bus_verify(bus, mb_def) is False


def test_motor_bus_verify_handles_tuple_ids_in_definition():
    manager = get_robot_manager()

    class FakeCanBus:
        def __init__(self):
            self.interface = "can1"
            self.baud_rate = 1000000
            self.motors = {}

    bus = FakeCanBus()
    mi = MotorModelInfo(model="DM4310", model_ids=[17168], limits={}, variant=None, brand=MotorBrand.DAMIAO)
    bus.motors = {(4, 0x14): (Mock(), mi)}

    # Provide tuple id in the definition (should be accepted and coerced)
    mb_def = MotorBusDefinition(type=bus.__class__.__name__, motors={
        "1": RobotMotorDefinition(name="1", id=(4, 0x14), brand="damiao", model="DM4310", variant=None),
    }, baud_rate=1000000)

    assert manager._motor_bus_verify(bus, mb_def) is True
