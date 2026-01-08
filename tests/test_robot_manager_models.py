# ruff: noqa
from leropilot.services.hardware.robots import RobotManager
from leropilot.models.hardware import (
    Robot,
    RobotDefinition,
    RobotMotorDefinition,
    MotorBusDefinition,
    RobotMotorBusConnection,
)


def test_get_robot_motor_models_info():
    manager = RobotManager()
    manager._robots.clear()

    # Ensure tables are loaded (registers models)
    from leropilot.services.hardware.motor_drivers import dynamixel, feetech

    rdef = RobotDefinition(
        id="",
        lerobot_name=None,
        display_name="test",
        description="",
        support_version_from=None,
        support_version_end=None,
        urdf=None,
        motor_buses={
            "mb": MotorBusDefinition(
                type="MockBus",
                motors={
                    "1": RobotMotorDefinition(name="1", id=1, brand="feetech", model="STS3215", variant=None),
                    "2": RobotMotorDefinition(name="2", id=2, brand="feetech", model="STS3215", variant="STS3215-C001"),
                    "3": RobotMotorDefinition(name="3", id=3, brand="dynamixel", model="AX-12A", variant=None),
                },
                baud_rate=None,
            )
        },
    )

    robot = Robot(id="R1", name="R1", definition=rdef)
    manager._robots[robot.id] = robot

    models = manager.get_robot_motor_models_info(robot.id)
    assert isinstance(models, list)
    assert len(models) == 3

    keys = {(m.brand.value if m.brand else "", m.model, m.variant) for m in models}
    assert ("feetech", "STS3215", None) in keys
    assert ("feetech", "STS3215", "STS3215-C001") in keys
    assert ("dynamixel", "AX-12A", None) in keys


def test_get_robot_motor_models_info_missing_robot():
    manager = RobotManager()
    manager._robots.clear()

    try:
        manager.get_robot_motor_models_info("NOPE")
        assert False, "Expected ValueError on missing robot"
    except ValueError:
        pass
