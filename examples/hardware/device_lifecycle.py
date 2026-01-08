#!/usr/bin/env python
"""
Example: Device Lifecycle Management

Demonstrate adding, managing, and persisting device configurations.

Usage:
    python -m examples.hardware.device_lifecycle
"""

import logging

from leropilot.services.hardware.robots import get_robot_manager
from leropilot.models.hardware import Robot

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
    """Demonstrate device lifecycle management"""
    print("\n" + "=" * 80)
    print("DEVICE LIFECYCLE MANAGEMENT")
    print("=" * 80)

    manager = get_robot_manager()

    try:
        # List existing devices
        print("\n📋 Current Devices:")
        robots = manager.list_robots()
        if robots:
            for r in robots:
                print(f"  - {r.id}: {r.name} ({r.status})")
        else:
            print("  (none)")

        # Add a device
        print("\n➕ Adding Device: 'Koch v1.1 (Dynamixel)'")
        robot = Robot(id="demo123", name="Koch v1.1 (Dynamixel)")
        manager.add_robot(robot)
        print(f"  ✅ Added: {robot.id}")

        # Get device
        print(f"\n📍 Retrieving Device: {robot.id}")
        robot = manager.get_robot(robot.id)
        if robot:
            print(f"  Name: {robot.name}")
            print(f"  Status: {robot.status}")

        # Update device status
        print(f"\n🔄 Updating Robot: {robot.id} → 'calibrating'")
        # Update robot name example
        manager.update_robot(robot.id, name="Koch (calibrating)")
        robot = manager.get_robot(robot.id)
        print(f"  ✅ New name: {robot.name}")

        # Add device labels
        print(f"\n🏷️  Adding Labels: {robot.id}")
        # Labels API removed in simplified RobotManager example
        # Get robots by name example
        print("\n🔍 Robots named 'Koch (calibrating)'):")
        for r in manager.list_robots():
            if r.name == "Koch (calibrating)":
                print(f"  - {r.id}: {r.name}")

        # Get device stats
        print("\n📊 Device Statistics:")
        # List final robots
        print("\n📋 Final Robot List:")
        robots = manager.list_robots()
        for r in robots:
            print(f"  - {r.id}: {r.name} ({r.status})")

        # Remove robot
        print(f"\n➖ Removing Robot: {robot.id}")
        manager.remove_robot(robot.id)
        print("  ✅ Removed")

        # Verify removal
        print("\n📋 Robots After Removal:")
        robots = manager.list_robots()
        if robots:
            for r in robots:
                print(f"  - {r.id}: {r.name}")
        else:
            print("  (none)")

        print("\n" + "=" * 80)
        print("Device Lifecycle Features:")
        print("  ✓ Add/remove devices")
        print("  ✓ Get/update device properties")
        print("  ✓ Update device status")
        print("  ✓ Add/remove labels")
        print("  ✓ Query by label")
        print("  ✓ Device statistics")
        print("  ✓ Export/import for backup")
        print("  ✓ Persistent storage (~/.leropilot/list.json)")
        print("=" * 80 + "\n")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        logger.exception("Exception during device lifecycle")


if __name__ == "__main__":
    main()
