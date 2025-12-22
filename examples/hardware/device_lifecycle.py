#!/usr/bin/env python
"""
Example: Device Lifecycle Management

Demonstrate adding, managing, and persisting device configurations.

Usage:
    python -m examples.hardware.device_lifecycle
"""

import logging

from leropilot.services.hardware.manager import get_hardware_manager

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
    """Demonstrate device lifecycle management"""
    print("\n" + "=" * 80)
    print("DEVICE LIFECYCLE MANAGEMENT")
    print("=" * 80)

    manager = get_hardware_manager()

    try:
        # List existing devices
        print("\n📋 Current Devices:")
        devices = manager.list_devices()
        if devices:
            for device in devices:
                print(f"  - {device.get('device_id')}: {device.get('name')} ({device.get('status')})")
        else:
            print("  (none)")

        # Add a device
        print("\n➕ Adding Device: 'Koch v1.1 (Dynamixel)'")
        device_id = manager.add_device(
            name="Koch v1.1 (Dynamixel)",
            device_type="hexapod",
            brand="dynamixel",
            port="COM3",
            baud_rate=1000000,
            status="connected",
        )
        print(f"  ✅ Added: {device_id}")

        # Get device
        print(f"\n📍 Retrieving Device: {device_id}")
        device = manager.get_device(device_id)
        if device:
            print(f"  Name: {device.get('name')}")
            print(f"  Type: {device.get('device_type')}")
            print(f"  Brand: {device.get('brand')}")
            print(f"  Port: {device.get('port')}")
            print(f"  Status: {device.get('status')}")

        # Update device status
        print(f"\n🔄 Updating Status: {device_id} → 'calibrating'")
        manager.set_device_status(device_id, "calibrating")
        device = manager.get_device(device_id)
        print(f"  ✅ New status: {device.get('status')}")

        # Add device labels
        print(f"\n🏷️  Adding Labels: {device_id}")
        manager.add_device_label(device_id, "production")
        manager.add_device_label(device_id, "hexapod")
        device = manager.get_device(device_id)
        print(f"  ✅ Labels: {device.get('labels')}")

        # Get devices by label
        print("\n🔍 Devices with label 'production':")
        production_devices = manager.get_devices_by_label("production")
        for device in production_devices:
            print(f"  - {device.get('device_id')}: {device.get('name')}")

        # Get device stats
        print("\n📊 Device Statistics:")
        stats = manager.get_device_stats()
        print(f"  Total devices: {stats.get('total_devices')}")
        print(f"  Statuses: {stats.get('status_counts')}")
        print(f"  Brands: {stats.get('brand_counts')}")
        print(f"  Types: {stats.get('type_counts')}")

        # List all devices after changes
        print("\n📋 Final Device List:")
        devices = manager.list_devices()
        for device in devices:
            print(f"  - {device.get('device_id')}: {device.get('name')} ({device.get('status')})")
            if device.get("labels"):
                print(f"    Labels: {', '.join(device.get('labels'))}")

        # Export devices
        print("\n💾 Exporting Devices:")
        exported = manager.export_devices()
        print(f"  ✅ Exported {len(exported)} device(s)")

        # Remove device
        print(f"\n➖ Removing Device: {device_id}")
        manager.remove_device(device_id)
        print("  ✅ Removed")

        # Verify removal
        print("\n📋 Devices After Removal:")
        devices = manager.list_devices()
        if devices:
            for device in devices:
                print(f"  - {device.get('device_id')}: {device.get('name')}")
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
