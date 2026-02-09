#!/usr/bin/env python3
r"""诊断脚本：快速检测 PCAN 接口与 Damiao 电机响应

用法（Windows cmd）:
  python examples\diagnose_damiao_pcan.py --interface "pcan:PCAN_USBBUS2" --baud 1000000

脚本会：
 - 连接到给定的 PCAN 接口
 - 打印 underlying CAN bus state（若可得）
 - 执行标准 scan_motors() 并打印结果
 - 如果 scan 失败，会用原始 REFRESH 命令探测 1..127 的 send id，记录回复的 arbitration ids
"""

from __future__ import annotations

import argparse
import sys
import time

from leropilot.services.hardware.motor_buses.motor_bus import MotorBus
from leropilot.services.hardware.motor_drivers.damiao.tables import DamiaoConstants


def probe_refresh(bus, send_id_range=range(1, 128), timeout_per_id=0.005):
    """Probe send IDs by sending a PARAM_ID refresh and collecting responses."""
    seen = set()
    msgs = []

    # Prepare refresh frames for each send id
    for sid in send_id_range:
        data = bytes([sid & 0xFF, (sid >> 8) & 0xFF, DamiaoConstants.CMD_REFRESH, 0, 0, 0, 0, 0])
        try:
            msg = bus.send(can_msg := type("M", (), {})())  # dummy to detect attribute errors if any
        except Exception:
            pass

    # Simpler: send a refresh for each id and try to recv for a short collective period
    start = time.time()
    for sid in send_id_range:
        try:
            data = bytes([sid & 0xFF, (sid >> 8) & 0xFF, DamiaoConstants.CMD_REFRESH, 0, 0, 0, 0, 0])
            msg = bus.send_message_to_param_id(data)
        except Exception:
            pass
        # collect a few ms
        t0 = time.time()
        while time.time() - t0 < timeout_per_id:
            m = bus.recv(0.002)
            if m:
                seen.add((m.arbitration_id, bytes(m.data)))
                msgs.append(m)
    return seen, msgs


def main() -> int:
    parser = argparse.ArgumentParser(description="Diagnose Damiao on PCAN interface")
    parser.add_argument("--interface", required=True)
    parser.add_argument("--baud", type=int, default=1000000)
    # args = parser.parse_args()

    # print(f"Using interface={args.interface} baud={args.baud}")

    try:
        mb = MotorBus.create("damiao", "pcan:PCAN_USBBUS2", 1000000)
    except Exception as e:
        print(f"Failed to create MotorBus: {e}")
        return 2

    try:
        # Connect and inspect driver/bus state
        mb.connect()
        print("Connected to motor bus")

        driver = mb.driver
        bus = getattr(driver, "bus", None)
        if bus is None:
            print("Underlying CAN bus object not available on driver")
        else:
            # Try to show state if present
            state = getattr(bus, "state", None)
            if state is not None:
                try:
                    print(f"CAN bus state: {state.name} ({int(state)})")
                except Exception:
                    print(f"CAN bus state: {state}")
            else:
                print("CAN bus has no 'state' attribute exposed")

        print("Running scan_motors()...")
        try:
            found = mb.scan_motors()
            print(f"scan_motors() found {len(found)} motors: {list(found.keys())}")
        except Exception as e:
            print(f"scan_motors() failed: {e}")

        # If nothing found, try probing refresh patterns and collecting any responses from bus.recv
        if not found:
            print("No motors discovered by scan_motors(); attempting low-level probe for responses.")

            # Use python-can recv directly for a short period to see any messages on bus
            any_msgs = []
            try:
                start = time.time()
                while time.time() - start < 0.5:
                    m = bus.recv(timeout=0.01)
                    if m:
                        any_msgs.append(m)
                print(
                    f"Saw {len(any_msgs)} raw messages in 0.5s: {[(hex(m.arbitration_id), bytes(m.data)) for m in any_msgs]}"
                )
            except Exception as e:
                print(f"Error while reading raw messages: {e}")

            # Try sending refresh to PARAM_ID for ids 1..32 quickly
            print("Sending refresh probes to PARAM_ID (1..32) and listening for replies")
            responses = {}
            try:
                for sid in range(1, 33):
                    data = bytes([sid & 0xFF, (sid >> 8) & 0xFF, DamiaoConstants.CMD_REFRESH, 0, 0, 0, 0, 0])
                    msg = driver._send_can_frame((sid, sid), data)  # best-effort send
                    # read short
                    t0 = time.time()
                    while time.time() - t0 < 0.01:
                        m = driver._recv_motor_response(timeout=0.005)
                        if m:
                            responses.setdefault(sid, []).append((m.arbitration_id, bytes(m.data)))
                print(f"Probe responses (1..32): {responses}")
            except Exception as e:
                print(f"Probing refresh failed: {e}")

    except Exception as e:
        print(f"Error during diagnostic: {e}")
        return 2
    finally:
        try:
            mb.disconnect()
        except Exception:
            pass

    return 0


if __name__ == "__main__":
    sys.exit(main())
