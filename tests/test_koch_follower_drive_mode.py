import json
from pathlib import Path


def test_koch_follower_all_drive_modes_zero():
    path = Path("src/leropilot/resources/robot_specs.json")
    data = json.loads(path.read_text(encoding='utf-8'))
    robots = data.get("robots", [])
    koch = next((r for r in robots if r.get("id") == "koch-follower"), None)
    assert koch is not None
    motors = koch.get("motor_buses", {}).get("motorbus", {}).get("motors", [])
    for m in motors:
        assert "drive_mode" not in m, f"Motor {m.get('name')} should not include drive_mode when default 0"
