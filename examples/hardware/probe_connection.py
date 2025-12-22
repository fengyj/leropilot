#!/usr/bin/env python
"""
Example: Probe Motor Connection

Auto-detect motor brand and optimal baud rate on a given serial port.

Usage:
    python -m examples.hardware.probe_connection <port>

Example:
    python -m examples.hardware.probe_connection COM3          # Windows
    python -m examples.hardware.probe_connection /dev/ttyUSB0  # Linux
"""

import logging
import sys
from leropilot.services.hardware.motors import MotorService

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def main():
    """Probe a serial port for connected motors"""
    if len(sys.argv) < 2:
        print("Usage: python probe_connection.py <port>")
        print("\nExamples:")
        print("  python probe_connection.py COM3")
        print("  python probe_connection.py /dev/ttyUSB0")
        sys.exit(1)

    port = sys.argv[1]
    service = MotorService()

    print("\n" + "=" * 60)
    print(f"PROBE MOTOR CONNECTION: {port}")
    print("=" * 60)

    try:
        result = service.probe_connection(interface=port)

        if result:
            print(f"✅ Motor Found!")
            print(f"  Interface: {result.interface} ({result.interface_type})")
            print(f"  Brand: {result.brand}")
            print(f"  Baud Rate: {result.baud_rate}")
            print(f"  Motor IDs: {[m.id for m in result.discovered_motors]}")
            print(f"  Motor Count: {len(result.discovered_motors)}")
            if result.suggested_robots:
                print(f"  Suggested Robots: {', '.join(result.suggested_robots)}")
        else:
            print("❌ No motors detected")
            print("  Check:")
            print("    - Serial port is correct")
            print("    - Motor is powered on")
            print("    - Motor is connected")
            print("    - Correct USB-to-serial adapter")

    except Exception as e:
        print(f"❌ Error during probe: {e}")
        logger.exception("Exception during probe")
    finally:
        print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
