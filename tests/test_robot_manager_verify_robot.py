import pytest

from leropilot.exceptions import ResourceConflictError, ValidationError
from leropilot.models.hardware import (
    MotorBrand,
    MotorBusDefinition,
    Robot,
    RobotDefinition,
    RobotMotorBusConnection,
    RobotMotorDefinition,
)
from leropilot.services.hardware.robots import RobotManager


def test_verify_robot_raises_on_missing_interface() -> None:
    manager = RobotManager()

    robot = Robot(
        id="r1",
        name="no-interface",
        motor_bus_connections={
            "mb": RobotMotorBusConnection(motor_bus_type="Fake", interface=None, baudrate=0)
        },
        definition=RobotDefinition(id="", display_name="no-interface", description="", motor_buses={}),
    )

    with pytest.raises(ValidationError) as exc:
        manager.verify_robot(robot)
    assert "interface" in str(exc.value).lower()


def test_verify_robot_invalid_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    manager = RobotManager()

    # Fake Bus implementation that connects but reports no motors
    class FakeBus:
        def __init__(self, interface: str, baud: int) -> None:
            self.interface = interface
            self.baud_rate = baud
            self.motors = {}

        def connect(self) -> bool:
            return True

        def disconnect(self) -> None:
            pass

        def scan_motors(self) -> dict:
            # no motors found
            return {}

    # Patch MotorBus.resolve_bus_class and create
    from leropilot.services.hardware.motor_buses import motor_bus as mbmod

    monkeypatch.setattr(mbmod.MotorBus, "resolve_bus_class", lambda t: FakeBus)
    monkeypatch.setattr(mbmod.MotorBus, "create", lambda cls, interface, baud: cls(interface, baud))

    # Definition expects a motor which won't be discovered -> should be INVALID
    robot = Robot(
        id="r2",
        name="invalid",
        motor_bus_connections={
            "motorbus": RobotMotorBusConnection(motor_bus_type="FakeBus", interface="ttyUSB0", baudrate=115200)
        },
        definition=RobotDefinition(
            id="",
            display_name="invalid",
            description="",
            motor_buses={
                "motorbus": MotorBusDefinition(
                    type="FakeBus",
                    motors={
                        "1": RobotMotorDefinition(
                            name="1",
                            id=1,
                            brand="feetech",
                            model="M1",
                            variant=None,
                            need_calibration=True,
                        )
                    },
                )
            },
        ),
    )

    with pytest.raises(ResourceConflictError) as exc:
        manager.verify_robot(robot)
    assert "invalid" in str(exc.value).lower()


    # Fake Bus implementation that reports one motor matching definition
    class FakeBusWithMotor:
        def __init__(self, interface: str, baud: int) -> None:
            self.interface = interface
            self.baud_rate = baud
            self.motors = {}

        def connect(self) -> bool:
            return True

        def disconnect(self) -> None:
            pass

        def scan_motors(self) -> dict:
            # Populate bus.motors with a single motor
            from leropilot.models.hardware import MotorModelInfo
            minfo = MotorModelInfo(model="M1", model_ids=[1], limits={}, variant=None, brand=MotorBrand.FEETECH)
            self.motors = {1: (object(), minfo)}
            return {1: minfo}

    from leropilot.services.hardware.motor_buses import motor_bus as mbmod

    monkeypatch.setattr(mbmod.MotorBus, "resolve_bus_class", lambda t: FakeBusWithMotor)
    monkeypatch.setattr(mbmod.MotorBus, "create", lambda cls, interface, baud: cls(interface, baud))

    robot = Robot(
        id="r3",
        name="available",
        motor_bus_connections={
            "motorbus": RobotMotorBusConnection(
                motor_bus_type="FakeBus",
                interface="ttyUSB1",
                baudrate=115200,
            )
        },
        definition=RobotDefinition(
            id="",
            display_name="available",
            description="",
            motor_buses={
                "motorbus": MotorBusDefinition(
                    type="FakeBus",
                    motors={
                        "1": RobotMotorDefinition(
                            name="1",
                            id=1,
                            brand="feetech",
                            model="M1",
                            variant=None,
                            need_calibration=True,
                        )
                    },
                )
            },
        ),
    )

    assert manager.verify_robot(robot) is True
