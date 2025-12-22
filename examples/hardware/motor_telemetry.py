#!/usr/bin/env python
"""
Example: Motor Telemetry Reading

Read position, velocity, and current from motors in real-time.

Usage:
    python -m examples.hardware.motor_telemetry <port> <brand> <motor_ids> [baud_rate]

Example:
    python -m examples.hardware.motor_telemetry COM3 dynamixel "1,2,3" 1000000
    python -m examples.hardware.motor_telemetry /dev/ttyUSB0 feetech "1" 1000000
"""

import logging
import sys
import time
from leropilot.services.hardware.motors import MotorService

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def main():
    """Read and display motor telemetry"""
    if len(sys.argv) < 4:
        print("Usage: python motor_telemetry.py <port> <brand> <motor_ids> [baud_rate]")
        print("\nExamples:")
        print("  python motor_telemetry.py COM3 dynamixel 1,2,3 1000000")
        print("  python motor_telemetry.py /dev/ttyUSB0 feetech 1 1000000")
        sys.exit(1)

    port = sys.argv[1]
    brand = sys.argv[2]
    motor_ids = [int(x.strip()) for x in sys.argv[3].split(",")]
    baud_rate = int(sys.argv[4]) if len(sys.argv) > 4 else 1000000

    service = MotorService()

    print("\n" + "=" * 80)
    print(f"MOTOR TELEMETRY READING")
    print(f"Port: {port}")
    print(f"Brand: {brand}")
    print(f"Motor IDs: {motor_ids}")
    print(f"Baud Rate: {baud_rate}")
    print("=" * 80)

    try:
        # Create driver
        driver = service.create_driver(interface=port, brand=brand, baud_rate=baud_rate)
        if not driver:
            print("❌ Failed to create driver")
            sys.exit(1)

        print(f"\n✅ Driver created: {driver.__class__.__name__}")

        # Read telemetry for 10 seconds
        print("\nReading telemetry (10 seconds):\n")
        print(f"{'Time (s)':<10} {'Motor ID':<10} {'Pos (rad)':<12} {'Vel (rad/s)':<12} {'Curr (mA)':<12}")
        print("-" * 60)

        start_time = time.time()
        read_count = 0

        while time.time() - start_time < 10:
            elapsed = time.time() - start_time

            for motor_id in motor_ids:
                try:
                    telemetry = driver.read_telemetry(motor_id)
                    if telemetry:
                        pos = telemetry.position
                        vel = telemetry.velocity
                        curr = telemetry.current
                        print(f"{elapsed:<10.2f} {motor_id:<10} {pos:<12.2f} {vel:<12.2f} {curr:<12.2f}")
                        read_count += 1
                except Exception as e:
                    logger.warning(f"Error reading motor {motor_id}: {e}")

            time.sleep(1)

        print("-" * 60)
        print(f"\n✅ Successfully read {read_count} telemetry samples")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        logger.exception("Exception during telemetry reading")
    finally:
        try:
            driver.disconnect()
        except Exception:
            pass
        print("\n" + "=" * 80 + "\n")


if __name__ == "__main__":
    main()
