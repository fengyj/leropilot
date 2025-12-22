#!/usr/bin/env python
"""
Example: Motor Bus Scanning

Scan a motor bus to enumerate motor IDs.

Usage:
    python -m examples.hardware.motor_scan <port> <brand> [baud_rate]

Example:
    python -m examples.hardware.motor_scan COM3 dynamixel 1000000
    python -m examples.hardware.motor_scan /dev/ttyUSB0 feetech 1000000
    python -m examples.hardware.motor_scan can0 damiao_can 1000000
"""

import logging
import sys

from leropilot.services.hardware.motors import MotorService

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
    """Scan a motor bus and enumerate motor IDs"""
    if len(sys.argv) < 3:
        print("Usage: python motor_scan.py <port> <brand> [baud_rate]")
        print("\nExamples:")
        print("  python motor_scan.py COM3 dynamixel 1000000")
        print("  python motor_scan.py /dev/ttyUSB0 feetech 1000000")
        print("  python motor_scan.py can0 damiao_can 1000000")
        print("\nBrands: dynamixel, feetech, damiao_can")
        sys.exit(1)

    port = sys.argv[1]
    brand = sys.argv[2]
    baud_rate = int(sys.argv[3]) if len(sys.argv) > 3 else 1000000

    service = MotorService()

    print("\n" + "=" * 60)
    print("MOTOR BUS SCAN")
    print(f"Port: {port}")
    print(f"Brand: {brand}")
    print(f"Baud Rate: {baud_rate}")
    print("=" * 60)

    try:
        # Create driver
        driver = service.create_driver(interface=port, brand=brand, baud_rate=baud_rate)

        if not driver:
            print("❌ Failed to create driver")
            sys.exit(1)

        print(f"\n✅ Driver created: {driver.__class__.__name__}")

        # Scan for motors
        print("\nScanning for motors (this may take 10-30 seconds)...")
        motor_ids = driver.scan_motors()

        if motor_ids:
            print(f"\n✅ Found {len(motor_ids)} motor(s):")
            # Sort by ID
            sorted_motors = sorted(motor_ids, key=lambda x: x.id)
            for motor in sorted_motors:
                print(f"  - Motor ID {motor.id} ({motor.model})")
        else:
            print("\n⚠️  No motors detected on this bus")
            print("  Check:")
            print("    - Motors are powered on")
            print("    - Motors are connected to bus")
            print("    - Correct port and baud rate")

    except Exception as e:
        print(f"\n❌ Error during scan: {e}")
        logger.exception("Exception during scan")
    finally:
        try:
            driver.disconnect()
        except Exception:
            pass
        print("\n" + "=" * 60 + "\n")


if __name__ == "__main__":
    main()
