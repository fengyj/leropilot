"""Service for managing robot configurations."""

import importlib.resources
import json
import logging
from pathlib import Path

from leropilot.models.hardware import MotorBrand, MotorInfo, RobotDefinition, SuggestedRobot

logger = logging.getLogger(__name__)


class RobotConfigService:
    """
    Service for loading and matching robot configurations.

    Loads robot definitions from robots.json and provides methods to match
    detected hardware against known robot models.
    """

    def __init__(self, config_path: Path | None = None) -> None:
        """
        Initialize robot config service.

        Args:
            config_path: Path to robots.json. If None, uses default resource path.
        """
        self.config_path = config_path
        self.robots = self._load_config()

    def _load_config(self) -> list[RobotDefinition]:
        """Load robot definitions from JSON."""
        try:
            if self.config_path is not None:
                # Load from explicit path
                if self.config_path.exists():
                    with open(self.config_path, encoding="utf-8") as f:
                        data = json.load(f)
                else:
                    logger.warning(f"Robots config not found at {self.config_path}")
                    return []
            else:
                # Load from package resources
                resource_files = importlib.resources.files("leropilot.resources")
                config_file = resource_files.joinpath("robots.json")
                with config_file.open("r", encoding="utf-8") as f:
                    data = json.load(f)

            robots_data = data.get("robots", [])
            robots = [RobotDefinition(**r) for r in robots_data]
            logger.info(f"Loaded {len(robots)} robot definitions")
            return robots
        except Exception as e:
            logger.error(f"Failed to load robots config: {e}")
            return []

    def get_robot_definition(self, robot_id: str) -> RobotDefinition | None:
        """
        Get robot definition by ID.

        Args:
            robot_id: Robot ID to look up

        Returns:
            RobotDefinition if found, None otherwise
        """
        for robot in self.robots:
            if robot.id == robot_id:
                return robot
        return None

    def suggest_robots(self, brand: MotorBrand, motors: list[MotorInfo]) -> list[SuggestedRobot]:
        """
        Suggest robot models based on detected motors.

        Args:
            brand: The motor brand detected on the bus
            motors: List of detected motors with ID and model info

        Returns:
            List of matching SuggestedRobot objects
        """
        detected_map = {m.id: m for m in motors}
        detected_ids = sorted(detected_map.keys())
        suggestions = []

        brand_str = brand.value.lower() if hasattr(brand, "value") else str(brand).lower()

        logger.debug(f"Suggesting robots for brand={brand_str}, ids={detected_ids}")

        for robot in self.robots:
            # Get motors from definition that match the current brand
            brand_motors = [m for m in robot.motors if m.brand.lower() == brand_str]

            if not brand_motors:
                continue

            # Check if the IDs match exactly for this brand's subset
            brand_ids = sorted([m.id for m in brand_motors])

            if brand_ids == detected_ids:
                # IDs match, now check models and variants for each motor
                match = True
                for req_motor in brand_motors:
                    mid = req_motor.id
                    det_motor = detected_map[mid]

                    # Check base model
                    if req_motor.model:
                        if req_motor.model.lower() not in det_motor.model.lower():
                            match = False
                            break

                    # Check variant (if specified in config)
                    if req_motor.variant and det_motor.variant:
                        # Only enforce variant match if the hardware actually reported one
                        if req_motor.variant.lower() not in det_motor.variant.lower():
                            match = False
                            break

                if match:
                    logger.info(f"Matched robot: {robot.display_name or robot.id}")
                    suggestions.append(
                        SuggestedRobot(
                            id=robot.id, lerobot_name=robot.lerobot_name or "", display_name=robot.display_name
                        )
                    )

        return suggestions
