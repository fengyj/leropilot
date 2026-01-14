import json
from pathlib import Path


def test_hopejr_hand_drive_modes() -> None:
    path = Path("src/leropilot/resources/robot_specs.json")
    assert path.exists(), "robot_specs.json not found"

    data = json.loads(path.read_text(encoding='utf-8'))
    robots = data.get("robots", [])
    # Combined model: hope-jr with left/right arms and hands
    hope = next((r for r in robots if r.get("id") == "hope-jr"), None)
    assert hope is not None, "hope-jr entry missing"

    left_hand = hope.get("motor_buses", {}).get("left_hand", {}).get("motors", [])
    right_hand = hope.get("motor_buses", {}).get("right_hand", {}).get("motors", [])
    name_map_left = {m.get("name"): m for m in left_hand}
    name_map_right = {m.get("name"): m for m in right_hand}

    right_inversions = [
        "thumb_mcp",
        "thumb_dip",
        "index_ulnar_flexor",
        "middle_ulnar_flexor",
        "ring_ulnar_flexor",
        "ring_pip_dip",
        "pinky_ulnar_flexor",
        "pinky_pip_dip",
    ]

    left_inversions = [
        "thumb_cmc",
        "thumb_mcp",
        "thumb_dip",
        "index_radial_flexor",
        "index_pip_dip",
        "middle_radial_flexor",
        "middle_pip_dip",
        "ring_radial_flexor",
        "ring_pip_dip",
        "pinky_radial_flexor",
    ]

    # Verify left-hand inversion flags
    for name in left_inversions:
        assert name in name_map_left, f"Motor '{name}' not found in hope-jr left_hand"
        m = name_map_left[name]
        assert m.get("drive_mode") == 1, f"Motor '{name}' in left_hand should have drive_mode 1"

    # Verify right-hand inversion flags
    for name in right_inversions:
        assert name in name_map_right, f"Motor '{name}' not found in hope-jr right_hand"
        m = name_map_right[name]
        assert m.get("drive_mode") == 1, f"Motor '{name}' in right_hand should have drive_mode 1"
