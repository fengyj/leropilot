import json
from pathlib import Path


def test_koch_leader_elbow_drive_mode():
    path = Path("src/leropilot/resources/robot_specs.json")
    assert path.exists(), "robot_specs.json not found"

    data = json.loads(path.read_text(encoding='utf-8'))
    robots = data.get("robots", [])
    koch = next((r for r in robots if r.get("id") == "koch-leader"), None)
    assert koch is not None, "koch-leader entry missing"

    motors = koch.get("motor_buses", {}).get("motorbus", {}).get("motors", [])
    elbow = next((m for m in motors if m.get("name") == "elbow_flex"), None)
    assert elbow is not None, "elbow_flex not found in koch-leader"
    assert elbow.get("drive_mode") == 1, "elbow_flex should have drive_mode 1"
