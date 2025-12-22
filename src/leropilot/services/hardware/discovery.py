"""
Cross-platform hardware discovery service.

Enumerates:
- Serial ports (with hardware serial numbers)
- USB cameras (USB video class)
- CAN interfaces (Linux only)
- RealSense depth cameras

Uses platform abstraction layer for OS-specific implementations.
Supports Windows, macOS, and Linux.
"""

import logging

from leropilot.models.hardware import (
    DeviceStatus,
    DiscoveredCamera,
    DiscoveredController,
    DiscoveredRobot,
    DiscoveryResult,
)
from leropilot.services.hardware.camera import CameraInfo, CameraService
from leropilot.services.hardware.platform_adapter import PlatformAdapter

logger = logging.getLogger(__name__)


class DiscoveryService:
    """Main hardware discovery service using platform adapter"""

    def __init__(self) -> None:
        """Initialize discovery service"""
        self.adapter = PlatformAdapter()
        self.camera_service = CameraService()
        logger.info(f"Discovery service initialized for {self.adapter.platform}")

    def discover_all(self) -> DiscoveryResult:
        """
        Perform full hardware discovery.

        Returns:
            DiscoveryResult with all discovered devices
        """
        logger.info("Starting hardware discovery...")

        # Use adapter to discover all devices (handles platform differences)
        serial_ports = self.adapter.discover_serial_ports()
        robots = self._serial_ports_to_robots(serial_ports)

        # Use CameraService which has complete metadata
        camera_infos = self.camera_service.list_cameras()
        cameras = self._camera_infos_to_discovered_cameras(camera_infos)

        can_interfaces = self.adapter.discover_can_interfaces()
        controllers = self._can_interfaces_to_controllers(can_interfaces)

        result = DiscoveryResult(
            robots=robots,
            controllers=controllers,
            cameras=cameras,
        )

        logger.info(f"Discovery complete: {len(robots)} robots, {len(controllers)} controllers, {len(cameras)} cameras")
        return result

    def discover_serial_ports(self) -> list[DiscoveredRobot]:
        """
        Discover only serial ports (robots).

        Returns:
            List of DiscoveredRobot objects
        """
        serial_ports = self.adapter.discover_serial_ports()
        return self._serial_ports_to_robots(serial_ports)

    def discover_cameras(self) -> list[DiscoveredCamera]:
        """
        Discover only cameras (USB + RealSense).

        Returns:
            List of DiscoveredCamera objects
        """
        camera_infos = self.camera_service.list_cameras()
        return self._camera_infos_to_discovered_cameras(camera_infos)

    def discover_can_interfaces(self) -> list[DiscoveredController]:
        """
        Discover only CAN interfaces (controllers).

        Returns:
            List of DiscoveredController objects
        """
        can_interfaces = self.adapter.discover_can_interfaces()
        return self._can_interfaces_to_controllers(can_interfaces)

    @staticmethod
    def _serial_ports_to_robots(serial_ports: list[dict]) -> list[DiscoveredRobot]:
        """Convert serial port data to DiscoveredRobot objects"""
        robots = []
        for port in serial_ports:
            # Filter: only include ports that look like motor controllers
            # (ignore debug ports, etc.)
            description = port.get("description", "").lower()
            if any(keyword in description for keyword in ["ftdi", "ch340", "prolific", "serial"]):
                robot = DiscoveredRobot(
                    port=port["port"],
                    description=port["description"],
                    serial_number=port.get("serial_number"),
                    manufacturer=port.get("manufacturer", "Unknown"),
                    vid=port["vid"],
                    pid=port["pid"],
                    status=DeviceStatus.AVAILABLE,
                )
                robots.append(robot)

        return robots

    @staticmethod
    def _camera_infos_to_discovered_cameras(camera_infos: list[CameraInfo]) -> list[DiscoveredCamera]:
        """Convert CameraInfo objects to DiscoveredCamera objects"""
        cameras = []
        for cam in camera_infos:
            # Generate instance_id from index and serial (if available)
            instance_id = f"cam_{cam.index}"
            if cam.serial_number:
                instance_id = f"cam_{cam.index}_{cam.serial_number}"

            camera = DiscoveredCamera(
                index=cam.index,
                instance_id=instance_id,
                name=cam.name,
                friendly_name=cam.name,
                type=cam.camera_type,  # "USB" or "RealSense"
                vid=cam.vid or "0000",
                pid=cam.pid or "0000",
                serial_number=cam.serial_number,
                manufacturer=cam.manufacturer or "Unknown",
                width=cam.width,
                height=cam.height,
                status=DeviceStatus.AVAILABLE,
            )
            cameras.append(camera)

        return cameras

    @staticmethod
    def _can_interfaces_to_controllers(can_interfaces: list[dict]) -> list[DiscoveredController]:
        """Convert CAN interface data to DiscoveredController objects"""
        controllers = []
        for interface in can_interfaces:
            controller = DiscoveredController(
                channel=interface["interface"],
                description=f"CAN Interface {interface['interface']}",
                vid="0000",
                pid="0000",
                manufacturer="Native",
                status=DeviceStatus.AVAILABLE,
            )
            controllers.append(controller)

        return controllers
