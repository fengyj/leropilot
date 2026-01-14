"""
Path utilities for robot data directory management.

This module provides helper functions for managing robot-related directories
and file paths in the application's data directory.
"""

from pathlib import Path


def get_robots_base_dir(create: bool = True) -> Path:
    """Return the base directory for robot persistent data: data_dir/hardwares/robots.

    Args:
        create: When True (default), ensure the directory exists.

    Returns:
        Path pointing to the robots directory.
    """
    from leropilot.services.config.manager import get_config

    cfg = get_config()
    data_dir = Path(cfg.paths.data_dir)
    robots_dir = data_dir / "hardwares" / "robots"
    if create:
        robots_dir.mkdir(parents=True, exist_ok=True)
    return robots_dir


def get_robot_list_path() -> Path:
    """Return the expected path to the persisted robots list.json (ensures parent dir exists)."""
    robots_dir = get_robots_base_dir(create=True)
    return robots_dir / "list.json"


def get_robot_base_dir(robot_id: str, create: bool = True) -> Path:
    """Return the per-robot base directory path (data_dir/hardwares/robots/<id>).

    Args:
        robot_id: Persisted robot id
        create: Whether to ensure the directory exists
    """
    robot_dir = get_robots_base_dir(create=True) / robot_id
    if create:
        robot_dir.mkdir(parents=True, exist_ok=True)
    return robot_dir


def get_robot_urdf_dir(robot_id: str, create: bool = True) -> Path:
    """Return the per-robot URDF directory path (data_dir/hardwares/robots/<id>/urdf).

    Args:
        robot_id: Persisted robot id
        create: Whether to ensure the directory exists
    """
    robot_dir = get_robot_base_dir(robot_id, create=True) / "urdf"
    if create:
        robot_dir.mkdir(parents=True, exist_ok=True)
    return robot_dir
