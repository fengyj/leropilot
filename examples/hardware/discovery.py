#!/usr/bin/env python
"""
Example: Hardware Discovery

Enumerate all connected hardware:
- Serial ports with motor controllers
- USB and RealSense cameras
- CAN interfaces

Usage:
    python -m examples.hardware.discovery
"""

import logging
from leropilot.services.hardware.discovery import DiscoveryService

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def main():
    """Discover and display all hardware"""
    service = DiscoveryService()

    print("\n" + "=" * 60)
    print("HARDWARE DISCOVERY EXAMPLE")
    print("=" * 60)

    # Discover all devices
    result = service.discover_all()

    # Display robots (serial ports)
    print(f"\n🤖 ROBOTS (Serial Ports): {len(result.robots)}")
    for robot in result.robots:
        print(f"  - {robot.port}")
        print(f"    Description: {robot.description}")
        print(f"    VID:PID: {robot.vid}:{robot.pid}")
        print(f"    Manufacturer: {robot.manufacturer}")
        if robot.serial_number:
            print(f"    Serial Number: {robot.serial_number}")
        print(f"    Status: {robot.status.value}")

    # Display controllers (CAN interfaces)
    print(f"\n🎮 CONTROLLERS (CAN): {len(result.controllers)}")
    for controller in result.controllers:
        print(f"  - {controller.channel}")
        print(f"    Description: {controller.description}")
        print(f"    Status: {controller.status.value}")

    # Display cameras
    print(f"\n📷 CAMERAS: {len(result.cameras)}")
    for camera in result.cameras:
        print(f"  - {camera.name} (index {camera.index}, {camera.type})")
        print(f"    Instance ID: {camera.instance_id}")
        print(f"    VID:PID: {camera.vid}:{camera.pid}")
        if camera.width and camera.height:
            print(f"    Resolution: {camera.width}x{camera.height}")
        if camera.serial_number:
            print(f"    Serial Number: {camera.serial_number}")
        print(f"    Manufacturer: {camera.manufacturer}")
        print(f"    Status: {camera.status.value}")

    print("\n" + "=" * 60)
    print(f"Total: {len(result.robots)} robots, {len(result.controllers)} controllers, {len(result.cameras)} cameras")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
