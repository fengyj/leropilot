import json
from pathlib import Path


def test_omx_follower_all_drive_modes_zero():
    path = Path("src/leropilot/resources/robot_specs.json")
    data = json.loads(path.read_text(encoding='utf-8'))
    robots = data.get("robots", [])
    omx_f = next((r for r in robots if r.get("id") == "omx-follower"), None)
    assert omx_f is not None
    motors = omx_f.get("motor_buses", {}).get("motorbus", {}).get("motors", [])
    for m in motors:
        assert "drive_mode" not in m, f"OMX follower motor {m.get('name')} should not include drive_mode when default 0"


def test_omx_leader_gripper_inverted():
    path = Path("src/leropilot/resources/robot_specs.json")
    data = json.loads(path.read_text(encoding='utf-8'))
    robots = data.get("robots", [])
    omx_l = next((r for r in robots if r.get("id") == "omx-leader"), None)
    assert omx_l is not None
    motors = omx_l.get("motor_buses", {}).get("motorbus", {}).get("motors", [])
    gripper = next((m for m in motors if m.get("name") == "joint_6"), None)
    assert gripper is not None
    assert gripper.get("drive_mode") == 1, "OMX leader gripper (joint_6) should have drive_mode 1"