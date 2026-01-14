"""
Robots service module.

This module consolidates robot discovery, configuration, and management services.
It provides a clean, modular architecture with separate concerns:

- paths: Path utilities for robot data directories
- spec_service: Robot specification loading and management
- discovery: Motor bus discovery and pending device building
- verification: Robot verification against actual hardware
- status_manager: Robot status management
- manager: Core robot CRUD operations and persistence
- calibration: Motor calibration data management
- urdf_manager: URDF file management

Public API:
- RobotManager: Core robot management (CRUD, persistence)
- RobotSpecService: Robot specification service
- RobotUrdfManager: URDF file management
- CalibrationService: Calibration data management
- get_robot_manager(): Get singleton RobotManager instance
- get_robot_urdf_manager(): Get singleton RobotUrdfManager instance
- Path utilities: get_robots_base_dir, get_robot_list_path, etc.
"""

from .calibration import CalibrationService
from .manager import RobotManager, get_robot_manager
from .paths import (
    get_robot_base_dir,
    get_robot_list_path,
    get_robot_urdf_dir,
    get_robots_base_dir,
)
from .spec_service import RobotSpecService
from .urdf_manager import RobotUrdfManager, get_robot_urdf_manager

__all__ = [
    # Core services
    "RobotManager",
    "RobotSpecService",
    "RobotUrdfManager",
    "CalibrationService",
    # Singleton accessors
    "get_robot_manager",
    "get_robot_urdf_manager",
    # Path utilities
    "get_robots_base_dir",
    "get_robot_list_path",
    "get_robot_base_dir",
    "get_robot_urdf_dir",
]
