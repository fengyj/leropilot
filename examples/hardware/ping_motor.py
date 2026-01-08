#!/usr/bin/env python3
"""
Simple ping utility for Damiao motors on a CAN interface.
Usage:
    python -m examples.hardware.ping_motor <interface> <motor_id>
Example:
    python -m examples.hardware.ping_motor PCAN_USBBUS1 3
"""

import sys
import logging
from typing import Optional

from leropilot.services.hardware.motor_drivers.damiao.drivers import DamiaoCAN_Driver

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def probe(interface: str, motor_id: int, baud: int = 1000000) -> None:
    print(f"=== Probe {interface} for motor {motor_id} @ {baud} bps ===")
    driver = DamiaoCAN_Driver(interface, baud)
    if not driver.connect():
        print(f"❌ Failed to connect to {interface}")
        return

    try:
        ping_ok = driver.ping_motor(motor_id)
        print(f"Ping motor {motor_id}: {ping_ok}")

        if ping_ok:
            telemetry = driver.read_telemetry(motor_id)
            print(f"Telemetry: {telemetry}")

            model = driver.identify_model(motor_id)
            if model:
                print(f"Identified model: {model.model} (variant: {model.variant}, ids: {model.model_ids})")
            else:
                print("Model identification failed or not available")
        else:
            # Try reading parameters as a second check
            param = driver.read_parameter(motor_id, 0x00)
            print(f"Parameter read (addr 0x00): {param}")

    except Exception as e:
        logger.error(f"Error probing {interface}: {e}")
    finally:
        driver.disconnect()


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python -m examples.hardware.ping_motor <interface> <motor_id>")
        sys.exit(1)

    interface = sys.argv[1]
    motor_id = int(sys.argv[2])
    probe(interface, motor_id)
