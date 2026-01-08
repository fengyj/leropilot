#!/usr/bin/env python3
"""Inspect a Damiao motor: ping, telemetry, parameter read and register on DamiaoMotorBus.

Usage:
    python -m examples.hardware.damiao_inspect <interface> <send_id> <recv_id>

Example:
    python -m examples.hardware.damiao_inspect pcan:PCAN_USBBUS2 3 19
"""

import sys
import logging

from leropilot.services.hardware.motor_drivers.damiao.drivers import DamiaoCAN_Driver
from leropilot.services.hardware.motor_buses.damiao_motor_bus import DamiaoMotorBus
from leropilot.models.hardware import MotorModelInfo, MotorBrand

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def main(interface: str, send_id: int, recv_id: int, baud: int = 1000000) -> None:
    print(f"=== Inspect Damiao motor on {interface} send={send_id} recv={recv_id} ===")

    motor_tuple = (int(send_id), int(recv_id))

    # Create a driver and connect
    driver = DamiaoCAN_Driver(interface, baud)
    if not driver.connect():
        print(f"❌ Failed to connect to {interface}")
        return

    try:
        # Ping using tuple id
        ping_ok = driver.ping_motor(motor_tuple)
        print(f"Ping ({motor_tuple}): {ping_ok}")

        # Read telemetry
        telemetry = driver.read_telemetry(motor_tuple)
        print(f"Telemetry: {telemetry}")

        # Identify model via parameter reads
        model = driver.identify_model(motor_tuple)
        print(f"Identified model: {model}")

        # Read a few parameters
        for addr in (0x00, 0x01, 0x100):
            val = driver.read_parameter(motor_tuple, addr)
            print(f"Param 0x{addr:02X} = {val}")

    except Exception as e:
        logger.error(f"Error probing motor: {e}")
    finally:
        # Register motor in a DamiaoMotorBus instance
        try:
            bus = DamiaoMotorBus(interface, bitrate=baud, motor_ids=[motor_tuple])
            if not bus.connect():
                logger.warning("DamiaoMotorBus connect failed (may be due to existing open channel), proceeding to register connected driver directly")

            # Use the already-connected driver ("driver") or create a separate one if needed
            try:
                mdrv = DamiaoCAN_Driver(interface, baud)
                if not mdrv.connect():
                    # Fallback: reuse the existing connected driver
                    logger.info("Could not create fresh motor driver; reusing main driver instance for registration")
                    mdrv = driver
                mdrv.motor_id = motor_tuple
                from leropilot.models.hardware import MotorModelInfo
                # Create a minimal MotorModelInfo for demonstration (real code should look up proper model table entries)
                mi = MotorModelInfo(model=model or "Unknown", model_ids=[0], limits={}, brand=MotorBrand.DAMIAO)
                bus.register_motor(mdrv.motor_id, mdrv, mi)
                print(f"Registered motor drivers on bus: {list(bus.motors.keys())}")
                # Try reading telemetry via bus
                tel2 = bus.read_telemetry(motor_tuple)
                print(f"Telemetry via bus: {tel2}")
            finally:
                # Disconnect the extra driver if we created one and it's not the primary driver
                if 'mdrv' in locals() and mdrv is not driver:
                    try:
                        mdrv.disconnect()
                    except Exception:
                        pass
            try:
                bus.disconnect()
            except Exception:
                pass
        except Exception as e:
            logger.error(f"Error registering motor on bus: {e}")

        driver.disconnect()


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: python -m examples.hardware.damiao_inspect <interface> <send_id> <recv_id>")
        sys.exit(1)

    iface = sys.argv[1]
    s = int(sys.argv[2])
    r = int(sys.argv[3])
    main(iface, s, r)