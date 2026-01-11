import json
from pathlib import Path

from leropilot.models.hardware import RobotDefinition, DeviceCategory


def test_robot_definition_device_category_loads():
    path = Path("src/leropilot/resources/robot_specs.json")
    assert path.exists(), "robot_specs.json not found"
    data = json.loads(path.read_text(encoding='utf-8'))
    robots = data.get("robots", [])
    assert robots, "No robots found in specs"

    for r in robots:
        rd = RobotDefinition.parse_obj(r)
        rid = r.get("id")
        if rid and rid.endswith("-leader"):
            expected = DeviceCategory.CONTROLLER
        else:
            expected = DeviceCategory.ROBOT
        assert rd.device_category == expected, f"Robot {rid} should have device_category={expected.value}"