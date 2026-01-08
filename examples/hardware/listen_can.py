#!/usr/bin/env python3
"""
Passive CAN listener for troubleshooting.
Usage:
    python -m examples.hardware.listen_can <interface> [baud_rate] [duration_seconds]
Example:
    python -m examples.hardware.listen_can PCAN_USBBUS2 1000000 8
"""

import sys
import time
import logging

import can

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def listen(interface: str, baud: int = 1000000, duration: float = 8.0) -> None:
    print(f"=== Listening on {interface} @ {baud} bps for {duration:.1f}s ===")
    try:
        bus = can.interface.Bus(channel=interface, interface="pcan", bitrate=baud)
    except Exception as e:
        print(f"❌ Failed to open CAN bus {interface}: {e}")
        return

    start = time.time()
    try:
        while time.time() - start < duration:
            msg = bus.recv(timeout=0.5)
            if msg:
                print(f"RECV: ID=0x{msg.arbitration_id:03X} LEN={len(msg.data)} DATA={msg.data.hex()}")
    except Exception as e:
        logger.error(f"Error while listening: {e}")
    finally:
        try:
            bus.shutdown()
        except Exception:
            pass


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m examples.hardware.listen_can <interface> [baud_rate] [duration_seconds]")
        sys.exit(1)

    iface = sys.argv[1]
    baud = int(sys.argv[2]) if len(sys.argv) > 2 else 1000000
    dur = float(sys.argv[3]) if len(sys.argv) > 3 else 8.0
    listen(iface, baud, dur)
