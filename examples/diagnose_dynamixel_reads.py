#!/usr/bin/env python3
"""Diagnostics: probe Dynamixel register read failures and Group* addParam behavior.

Run this on the machine with the motors connected. It will:
- Connect to the first pending device's motor bus (like monitor example)
- Scan motors and print discovered IDs and models
- For each motor, attempt individual reads for suspect registers and print raw SDK results
- Attempt GroupBulkRead.addParam and GroupSyncRead.addParam to observe return values/exceptions

Usage: python examples/diagnose_dynamixel_reads.py
"""

from __future__ import annotations

import sys
from typing import Any

from leropilot.models.hardware import RobotMotorBusConnection
from leropilot.services.hardware.motor_buses.motor_bus import MotorBus
from leropilot.services.hardware.motor_drivers.dynamixel.tables import DynamixelRegisters
from leropilot.services.hardware.robots.manager import get_robot_manager

SUSPECT_REGISTERS = [
    DynamixelRegisters.PRESENT_POSITION,
    DynamixelRegisters.PRESENT_VELOCITY,
    DynamixelRegisters.PRESENT_CURRENT,
    DynamixelRegisters.PRESENT_VOLTAGE,
    DynamixelRegisters.PRESENT_TEMPERATURE,
]


def fmt(val: Any) -> str:
    if val is None:
        return "None"
    return str(val)


def main() -> int:
    rm = get_robot_manager()
    pending = rm.get_pending_devices()
    if not pending:
        print("No pending devices found")
        return 1

    robot = pending[0]
    print(f"Selected device: id={robot.id} name={robot.name} status={robot.status}")

    mb_conns = robot.motor_bus_connections or {}
    if not mb_conns:
        print("No motor bus connections available on this device")
        return 1

    conn_name, conn = next(iter(mb_conns.items()))
    if not isinstance(conn, RobotMotorBusConnection):
        conn = RobotMotorBusConnection(**conn)  # type: ignore[arg-type]

    print(f"Using motor bus connection: name={conn_name} interface={conn.interface} baud={conn.baudrate}")

    try:
        mb = MotorBus.create(conn.motor_bus_type)
        mb.connect(conn.interface, conn.baudrate)
    except Exception as e:
        print(f"Failed to create motor bus: {e}")
        return 1

    with mb:
        # Limit scan to first 16 IDs for quicker diagnostics
        discovered = mb.scan_motors(list(range(1, 17)))
        if not discovered:
            print("No motors discovered on bus (tried IDs 1..16)")
            return 1

        print(f"Discovered motors: {discovered}")

        driver = mb.driver
        if driver is None:
            print("No driver available")
            return 1

        ph = driver.packet_handler
        port = driver.port_handler

        # Try bulk/group addParam behaviors
        print("\nTesting GroupSyncRead.addParam behavior and individual register reads")
        for mid, model in discovered.items():
            print(f"Motor {mid}: model={model.model} encoder_res={model.encoder_resolution}")
            for addr, length in SUSPECT_REGISTERS:
                print(f"  Register addr={addr} len={length}")
                # Individual read attempts
                try:
                    if length == 4:
                        res, dxl_comm_result, dxl_err = ph.read4ByteTxRx(port, mid, addr)
                    elif length == 2:
                        res, dxl_comm_result, dxl_err = ph.read2ByteTxRx(port, mid, addr)
                    elif length == 1:
                        res, dxl_comm_result, dxl_err = ph.read1ByteTxRx(port, mid, addr)
                    else:
                        print("    Unsupported length for individual read")
                        continue
                    print(f"    Individual read -> result={fmt(res)} comm={dxl_comm_result} err={dxl_err}")
                except Exception as e:
                    print(f"    Individual read exception: {e}")

                # Try GroupSyncRead.addParam (with start_address & data_length set)
                if driver.group_sync_read:
                    try:
                        # Clear then set attributes if supported
                        try:
                            driver.group_sync_read.clearParam()
                        except Exception:
                            pass
                        try:
                            driver.group_sync_read.start_address = addr
                            driver.group_sync_read.data_length = length
                        except Exception:
                            pass
                        ok = driver.group_sync_read.addParam(mid)
                        print(f"    GroupSyncRead.addParam -> {ok}")
                    except Exception as e:
                        print(f"    GroupSyncRead.addParam exception: {e}")

        print("\nDone diagnostics")
    return 0


if __name__ == "__main__":
    sys.exit(main())
