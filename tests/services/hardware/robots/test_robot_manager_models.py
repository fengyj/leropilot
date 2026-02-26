# ruff: noqa
from leropilot.services.hardware.robots import RobotManager
from leropilot.models.hardware import (
    Robot,
    RobotDefinition,
    RobotMotorDefinition,
    MotorBusDefinition,
    MotorNormMode,
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

    robot = Robot(id="R1", name="R1", definition=rdef, is_calibrated=False)
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


def test_add_robot_initializes_default_calibration_settings(monkeypatch):
    """Ensure service layer creates default calibration entries for all definition motors."""
    manager = RobotManager()
    manager._robots.clear()

    monkeypatch.setattr(manager, "verify_robot", lambda robot: True)
    monkeypatch.setattr(manager, "_save_robots", lambda: None)

    rdef = RobotDefinition(
        id="demo",
        lerobot_name=None,
        display_name="demo",
        description="demo",
        support_version_from=None,
        support_version_end=None,
        urdf=None,
        motor_buses={
            "motorbus": MotorBusDefinition(
                type="FeetechMotorBus",
                motors={
                    "joint_1": RobotMotorDefinition(
                        name="joint_1",
                        id=1,
                        brand="feetech",
                        model="STS3215",
                        variant=None,
                        drive_mode=0,
                        norm_mode=MotorNormMode.RANGE_M100_100,
                    )
                },
                baud_rate=1000000,
            )
        },
    )

    robot = Robot(
        id="R_CAL_INIT",
        name="R_CAL_INIT",
        definition=rdef,
        motor_bus_connections={
            "motorbus": RobotMotorBusConnection(
                motor_bus_type="FeetechMotorBus",
                interface="COM9",
                baudrate=1000000,
                serial_number=None,
            )
        },
        calibration_settings={},
        is_calibrated=False,
    )

    added = manager.add_robot(robot)

    assert "motorbus" in added.calibration_settings
    assert len(added.calibration_settings["motorbus"]) == 1
    cal = added.calibration_settings["motorbus"][0]
    assert cal.id == 1
    assert cal.name == "joint_1"
    assert cal.range_max > 0
