#!/usr/bin/env python3
"""
Send a raw CAN frame (single-byte refresh) like PCAN-View does and listen for replies.
Usage:
    python -m examples.hardware.raw_ping <interface> [baud_rate]
Example:
    python -m examples.hardware.raw_ping PCAN_USBBUS1 1000000
"""

import sys
import time
import logging

import can

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def raw_ping(interface: str, baud: int = 1000000, target_id: int = 3, listen_time: float = 3.0) -> None:
    print(f"=== Raw ping {interface} -> ID {target_id} (0x{target_id:02X}) @ {baud} bps ===")

    # Open can bus (pcan type for PCAN adapters)
    try:
        bus = can.interface.Bus(channel=interface, bustype="pcan", bitrate=baud)
    except Exception as e:
        print(f"❌ Failed to open CAN bus {interface}: {e}")
        return

    try:
        # Build frame like PCAN-View shows: first byte = 0xCC, pad to 8 bytes
        data = bytes([0xCC] + [0x00] * 7)
        msg = can.Message(arbitration_id=target_id, data=data, is_extended_id=False)

        print(f"Sending: ID=0x{target_id:03X} data={data.hex()}")
        bus.send(msg)

        print(f"Listening for responses for {listen_time:.1f}s...")
        start = time.time()
        while time.time() - start < listen_time:
            m = bus.recv(timeout=0.5)
            if m is None:
                continue
            # Print raw message
            print(f"RECV: ID=0x{m.arbitration_id:03X} LEN={len(m.data)} DATA={m.data.hex()}")
    except Exception as e:
        logger.error(f"Error during raw ping: {e}")
    finally:
        try:
            bus.shutdown()
        except Exception:
            pass


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m examples.hardware.raw_ping <interface> [baud_rate]")
        sys.exit(1)

    iface = sys.argv[1]
    baud = int(sys.argv[2]) if len(sys.argv) > 2 else 1000000
    raw_ping(iface, baud)