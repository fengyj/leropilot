from leropilot.models.hardware import RobotMotorDefinition


def test_robot_motor_definition_int():
    m = RobotMotorDefinition(id=3, brand="damiao", model="DM4310")
    assert m.id == 3
    assert m.recv_id == 3


def test_robot_motor_definition_tuple():
    m = RobotMotorDefinition(id=(3, 0x13), brand="damiao", model="DM4310")
    assert m.id == 3
    assert m.recv_id == 0x13
