"""
Robot status management service.

This module handles refreshing robot status based on discovered hardware.
"""

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:

    from .discovery import MotorBusDiscovery
    from .verification import RobotVerificationService

from leropilot.models.hardware import Robot

logger = logging.getLogger(__name__)


class RobotStatusManager:
    """Service for managing robot online/offline status."""

    def __init__(
        self,
        discovery_service: "MotorBusDiscovery",
        verification_service: "RobotVerificationService",
    ) -> None:
        """
        Initialize status manager.

        Args:
            discovery_service: Service for discovering motor buses
            verification_service: Service for verifying robots
        """
        self._discovery = discovery_service
        self._verifier = verification_service

    def refresh_robot_status(
        self, robots: dict[str, Robot], robot_id: str | None = None
    ) -> tuple[list[str], list[Robot]]:
        """Refresh online/status state for a robot or all robots.

        Args:
            robots: Dictionary of all robots (id -> Robot)
            robot_id: Optional robot id to refresh (otherwise refresh all)

        Returns:
            Tuple of (removed_robot_ids, updated_robots_list)
        """
        # Determine subset of robots to process
        to_process: list[tuple[str, Robot]] = []
        if robot_id is not None:
            r = robots.get(robot_id)
            if r is None:
                return ([], [])
            to_process = [(robot_id, r)]
        else:
            to_process = list(robots.items())

        # Aggregate filters (motorbus type, baudrate) from robots we will inspect
        filters = self._build_discovery_filters(to_process)

        # Discover available motorbuses (restrict by filters for efficiency)
        discovered = self._discovery.discover_motor_buses(filters if filters else None)

        # Check status for each robot
        removed_ids: list[str] = []
        for rid, robot in to_process:
            new_status, should_remove = self._verifier.check_robot_status(robot, discovered)

            if should_remove:
                # Robot is transient and offline -> mark for removal
                removed_ids.append(rid)
            else:
                robot.status = new_status

        return (removed_ids, list(robots.values()))

    def _build_discovery_filters(self, robots_to_check: list[tuple[str, Robot]]) -> list[tuple[str, int | None]]:
        """Build discovery filters from robots to check."""
        filters: list[tuple[str, int | None]] = []
        for _, robot in robots_to_check:
            defn = robot.definition
            if isinstance(defn, str):
                raise ValueError("Robot.definition must be a RobotDefinition, not a string")
            if not defn or not getattr(defn, "motor_buses", None):
                continue
            for key, _conn in (robot.motor_bus_connections or {}).items():
                mb = None
                try:
                    mb = defn.motor_buses.get(key)
                except Exception:
                    mb = None
                if mb is None:
                    continue
                filters.append((mb.type, mb.baud_rate or 0))

        return filters
