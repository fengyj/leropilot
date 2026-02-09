from pathlib import Path
from types import SimpleNamespace

import pytest

from leropilot.services.hardware.robots import (
    get_robot_list_path,
    get_robot_urdf_dir,
    get_robots_base_dir,
)


def test_robot_paths_helpers_create_dirs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Arrange: point config to temporary data dir
    data_dir = tmp_path / "data"
    cfg = SimpleNamespace(paths=SimpleNamespace(data_dir=str(data_dir)))
    monkeypatch.setattr("leropilot.services.config.manager.get_config", lambda: cfg)

    # Act
    robots_dir = get_robots_base_dir(create=True)
    list_path = get_robot_list_path()
    urdf_dir = get_robot_urdf_dir("robot123", create=True)

    # Assert
    assert robots_dir.exists()
    assert robots_dir == data_dir / "hardwares" / "robots"
    assert list_path.parent.exists()
    assert list_path.name == "list.json"
    assert urdf_dir.exists()
    assert urdf_dir == data_dir / "hardwares" / "robots" / "robot123" / "urdf"
