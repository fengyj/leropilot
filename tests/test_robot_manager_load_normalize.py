import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from leropilot.services.hardware.robots import RobotManager, get_robot_list_path


def test_load_robots_normalizes_legacy_entries(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Arrange: point config to temporary data dir
    data_dir = tmp_path / "data"
    cfg = SimpleNamespace(paths=SimpleNamespace(data_dir=str(data_dir)))
    monkeypatch.setattr("leropilot.services.config.manager.get_config", lambda: cfg)

    # Create a legacy-style list.json: missing `interface` on motor bus and
    # comma-separated key in custom_protection_settings
    list_path = get_robot_list_path()
    list_path.parent.mkdir(parents=True, exist_ok=True)

    robot = {
        "id": "test-robot-1",
        "name": "Test Robot",
        "status": "available",
        "is_transient": False,
        "custom_protection_settings": {
            "damiao,dm4340,DM4340P": [
                {"type": "voltage_min", "value": 12.0}
            ]
        },
        "motor_bus_connections": {
            "motorbus": {"motor_bus_type": "DamiaoMotorBus", "baudrate": 1000000, "serial_number": "ABC"}
        },
    }

    with open(list_path, "w", encoding="utf-8") as f:
        json.dump({"robots": [robot]}, f)

    # Act
    manager = RobotManager()
    manager._robots.clear()
    manager._load_robots()

    # Assert
    assert "test-robot-1" in manager._robots
    r = manager._robots["test-robot-1"]
    # motor bus interface should be present (None) after normalization
    assert r.motor_bus_connections["motorbus"].interface is None
    # custom_protection_settings key should be normalized to a tuple
    keys = list(r.custom_protection_settings.keys())
    assert ("damiao", "dm4340", "DM4340P") in keys
