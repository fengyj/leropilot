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

from leropilot.services.hardware.platform_adapter import PlatformAdapter as DiscoveryService

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
    """Discover and display all hardware"""
    service = DiscoveryService()

    print("\n" + "=" * 60)
    print("HARDWARE DISCOVERY EXAMPLE")
    print("=" * 60)

    # Discover serial ports and CAN interfaces
    serial_ports = service.discover_serial_ports()
    can_interfaces = service.discover_can_interfaces()

    # Filter serial ports that look like motor controllers
    robot_ports = [p for p in serial_ports if any(k in p.get("description", "").lower() for k in ["ftdi", "ch340", "prolific", "serial"])]

    print(f"\n🤖 ROBOTS (Serial Ports): {len(robot_ports)}")
    for port in robot_ports:
        print(f"  - {port.get('port')}")
        print(f"    Description: {port.get('description')}")
        print(f"    VID:PID: {port.get('vid', '0000')}:{port.get('pid', '0000')}")
        print(f"    Manufacturer: {port.get('manufacturer', 'Unknown')}")
        if port.get('serial_number'):
            print(f"    Serial Number: {port.get('serial_number')}")

    print(f"\n🎮 CONTROLLERS (CAN): {len(can_interfaces)}")
    for interface in can_interfaces:
        print(f"  - {interface.get('interface')}")
        print(f"    Description: {interface.get('description', f'CAN Interface {interface.get(\'interface\')}')}")

    print("\n" + "=" * 60)
    print(f"Total: {len(robot_ports)} robots, {len(can_interfaces)} controllers")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
