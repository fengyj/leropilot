"""
Robot specification service.

This module provides the RobotSpecService class for loading and accessing
robot definitions from robot_specs.json.
"""

import importlib.resources
import json
import logging
from pathlib import Path

from leropilot.models.hardware import RobotDefinition

logger = logging.getLogger(__name__)


class RobotSpecService:
    """
    Service for loading robot specifications.

    Loads robot definitions from `robot_specs.json` and provides methods to
    access the definitions. The loaded specs are cached in memory.
    """

    def __init__(self, config_path: Path | None = None) -> None:
        """
        Initialize robot spec service.

        Args:
            config_path: Optional path to `robot_specs.json`. If not provided, the
                         service will attempt to load from package resources via
                         `leropilot.utils.get_resources_dir()` or fallback to
                         `importlib.resources`.
        """
        self.config_path = config_path
        self._cached: list[RobotDefinition] | None = None

    def _load_config(self) -> list[RobotDefinition]:
        """Load robot specifications from JSON and cache the result."""
        try:
            data = None
            if self.config_path is not None:
                if self.config_path.exists():
                    with open(self.config_path, encoding="utf-8") as f:
                        data = json.load(f)
                else:
                    logger.warning(f"Robot specs not found at {self.config_path}")
            else:
                # Prefer configured resources dir when available
                try:
                    from leropilot.utils.paths import get_resources_dir

                    resources_dir = get_resources_dir()
                    spec_file = resources_dir / "robot_specs.json"
                    if spec_file.exists():
                        with open(spec_file, encoding="utf-8") as f:
                            data = json.load(f)
                    else:
                        # Fallback to package resource
                        resource_files = importlib.resources.files("leropilot.resources")
                        config_file = resource_files.joinpath("robot_specs.json")
                        with config_file.open("r", encoding="utf-8") as f:
                            data = json.load(f)
                except Exception:
                    # Final fallback: importlib.resources directly
                    resource_files = importlib.resources.files("leropilot.resources")
                    config_file = resource_files.joinpath("robot_specs.json")
                    with config_file.open("r", encoding="utf-8") as f:
                        data = json.load(f)

            robots_data = (data or {}).get("robots", [])
            robots = [RobotDefinition(**r) for r in robots_data]
            # Sort robots by display_name for consistent UI presentation
            def _get_sort_key(r: RobotDefinition) -> str:
                if isinstance(r.display_name, str):
                    return r.display_name
                # Use "en" as fallback for sorting if it's a dict
                return r.display_name.get("en") or (list(r.display_name.values())[0] if r.display_name else "")

            robots.sort(key=_get_sort_key)
            logger.info(f"Loaded {len(robots)} robot specifications")
            return robots
        except Exception as e:
            logger.error(f"Failed to load robot specifications: {e}")
            return []

    def get_all_definitions(self) -> list[RobotDefinition]:
        """Return all robot definitions, loading and caching them if necessary."""
        if self._cached is None:
            self._cached = self._load_config()
        return self._cached

    def get_robot_definition(self, robot_id: str) -> RobotDefinition | None:
        """
        Get robot definition by ID.

        Args:
            robot_id: Robot ID to look up

        Returns:
            RobotDefinition if found, None otherwise
        """
        for robot in self.get_all_definitions():
            if robot.id == robot_id:
                return robot
        return None
