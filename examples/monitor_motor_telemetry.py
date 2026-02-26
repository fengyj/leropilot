#!/usr/bin/env python3
"""示例脚本：查询已接入设备、创建 MotorBus、禁用所有电机 torque，并以 10fps 原位更新输出每个电机的 telemetry（position 为 raw）。

用法：python examples/monitor_motor_telemetry.py
"""

from __future__ import annotations

import os
import sys
import time
from typing import Any

from leropilot.models.hardware import PositionType, RobotMotorBusConnection
from leropilot.services.hardware.motor_buses.motor_bus import MotorBus
from leropilot.services.hardware.robots.manager import get_robot_manager


def format_motor_id(mid: Any) -> str:
    """格式化 motor id，兼容 int 或 (send, recv) tuple。"""
    if isinstance(mid, (list, tuple)):
        return ":".join(str(int(x)) for x in mid)
    return str(mid)


def render_table(headers: list[str], rows: list[list[str]], use_unicode: bool | None = None) -> str:
    """Render a simple table using Unicode box-drawing characters when supported.

    If `use_unicode` is None the function will attempt to detect UTF-8 capable
    terminals and fall back to an ASCII table otherwise.
    """

    def _detect_unicode_support() -> bool:
        enc = (getattr(sys.stdout, "encoding", None) or "").lower()
        if "utf" in enc:
            return True
        # Heuristic checks for Windows terminals that support Unicode
        if os.name == "nt":
            if os.environ.get("WT_SESSION") or os.environ.get("ANSICON"):
                return True
            term = os.environ.get("TERM", "").lower()
            if term in ("xterm-256color", "xterm"):
                return True
        return False

    if use_unicode is None:
        use_unicode = _detect_unicode_support()

    # Compute column widths
    col_widths: list[int] = []
    for i, h in enumerate(headers):
        max_cell = max((len(row[i]) for row in rows), default=0) if rows else 0
        col_widths.append(max(len(h), max_cell))

    # Choose border characters
    if use_unicode:
        tl, tm, tr = "┌", "┬", "┐"
        ml, mm, mr = "├", "┼", "┤"
        bl, bm, br = "└", "┴", "┘"
        hor, ver = "─", "│"
    else:
        tl = tm = tr = "+"
        ml = mm = mr = "+"
        bl = bm = br = "+"
        hor, ver = "-", "|"

    top = tl + tm.join(hor * (w + 2) for w in col_widths) + tr
    header_sep = ml + mm.join(hor * (w + 2) for w in col_widths) + mr
    bottom = bl + bm.join(hor * (w + 2) for w in col_widths) + br

    header_row = ver + ver.join(f" {h.center(w)} " for h, w in zip(headers, col_widths)) + ver

    lines: list[str] = [top, header_row, header_sep]

    # Decide alignment per column: first column left, numeric/right-aligned, moving centered
    aligns: list[str] = []
    for h in headers:
        if h == headers[0]:
            aligns.append("left")
        elif h == "moving":
            aligns.append("center")
        else:
            aligns.append("right")

    for r in rows:
        cells: list[str] = []
        for i, c in enumerate(r):
            w = col_widths[i]
            s = str(c)
            if aligns[i] == "left":
                cells.append(s.ljust(w))
            elif aligns[i] == "center":
                cells.append(s.center(w))
            else:
                cells.append(s.rjust(w))
        lines.append(ver + ver.join(f" {cell} " for cell in cells) + ver)

    lines.append(bottom)
    return "\n".join(lines)


def main() -> int:
    rm = get_robot_manager()

    pending = rm.get_pending_devices()
    if not pending:
        print("未发现任何接入设备（pending devices 为空）。请先连接设备或运行 discovery。")
        return 1

    # 选择第一个设备
    robot = pending[0]
    print(f"选中设备: id={robot.id} name={robot.name} status={robot.status}")

    mb_conns = robot.motor_bus_connections or {}
    if not mb_conns:
        print("选中设备没有 motor_bus_connections 信息，无法继续。")
        return 1

    # 任选其中一个连接
    conn_name, conn = next(iter(mb_conns.items()))
    if not isinstance(conn, RobotMotorBusConnection):
        # 兼容未解析的 dict 情形
        conn = RobotMotorBusConnection(**conn)  # type: ignore[arg-type]

    print(
        f"使用 motor bus 连接: name={conn_name} type={conn.motor_bus_type} interface={conn.interface} baud={conn.baudrate}"
    )

    # 创建 MotorBus 实例并 connect（使用上下文管理器确保退出时 disconnect）
    try:
        mb = MotorBus.create(conn.motor_bus_type)
        mb.connect(conn.interface, conn.baudrate)
    except Exception as e:
        print(f"无法创建 MotorBus: {e}")
        return 1

    try:
        with mb:
            print("已连接到 motor bus，开始扫描电机...")
            discovered = mb.scan_motors()
            if not discovered:
                print("未在该 bus 上发现任何电机。")
                return 1

            motor_ids = list(discovered.keys())
            print(f"发现 {len(motor_ids)} 个电机: {[format_motor_id(mid) for mid in motor_ids]}")

            # 禁用所有电机 torque
            torque_results = mb.bulk_set_torque(motor_ids, enabled=False)
            failed = [format_motor_id(mid) for mid, ok in torque_results.items() if not ok]
            if failed:
                print(f"禁用 torque 时部分失败: {failed}")

            # 尝试读取扭矩 enable 状态（若 driver 支持）
            try:
                driver = mb._ensure_driver()
                # 根据不同驱动使用对应的寄存器读取方法
                from leropilot.services.hardware.motor_drivers.dynamixel.drivers import DynamixelDriver
                from leropilot.services.hardware.motor_drivers.feetech.drivers import FeetechDriver

                if isinstance(driver, DynamixelDriver):
                    from leropilot.services.hardware.motor_drivers.dynamixel.tables import DynamixelRegisters

                    raw_vals = driver.bulk_read_registers(
                        motor_ids, DynamixelRegisters.TORQUE_ENABLE[0], DynamixelRegisters.TORQUE_ENABLE[1]
                    )
                    print("Torque enable states (Dynamixel):")
                    for mid in motor_ids:
                        v = raw_vals.get(mid)
                        if v is None:
                            state = "no data"
                        else:
                            state = "enabled" if int(v) != 0 else "disabled"
                        print(f"  {format_motor_id(mid)}: {state}")
                elif isinstance(driver, FeetechDriver):
                    from leropilot.services.hardware.motor_drivers.feetech.tables import SCS_STS_Registers

                    raw_vals = driver.bulk_read_registers(
                        motor_ids, SCS_STS_Registers.TORQUE_ENABLE[0], SCS_STS_Registers.TORQUE_ENABLE[1]
                    )
                    print("Torque enable states (Feetech):")
                    for mid in motor_ids:
                        v = raw_vals.get(mid)
                        if v is None:
                            state = "no data"
                        else:
                            state = "enabled" if int(v) != 0 else "disabled"
                        print(f"  {format_motor_id(mid)}: {state}")
                else:
                    # Damiao 等驱动通常没有可读取的 torque enable 寄存器
                    print(f"Driver {driver.__class__.__name__} 不支持读取 torque enable 状态，跳过。")
            except Exception as e:
                print(f"读取 torque 状态时出错: {e}")

            # 降低默认帧率以减少闪烁
            target_fps = 5
            sleep_time = 1.0 / target_fps

            print(f"开始以 {target_fps}fps 循环读取 telemetry，按 Ctrl-C 停止。")

            try:
                first_frame = True
                prev_lines = 0
                while True:
                    telemetry_map = mb.bulk_read_telemetry(motor_ids, position_type=PositionType.RAW)

                    headers = ["motor_id", "position(raw)", "vel(rad/s)", "current(mA)", "temp(C)", "moving", "error"]
                    rows: list[list[str]] = []
                    for mid in motor_ids:
                        t = telemetry_map.get(mid)
                        if t is None:
                            rows.append([format_motor_id(mid), "<no data>", "", "", "", "", ""])
                            continue

                        if t.position is None:
                            pos = "N/A"
                        else:
                            # Show raw counts as integers for PositionType.RAW to avoid confusion
                            if t.position_type == PositionType.RAW:
                                pos = str(int(round(t.position)))
                            else:
                                pos = f"{t.position:.4f}"
                        vel = f"{t.velocity:.4f}" if t.velocity is not None else "N/A"
                        curr = f"{t.current:.1f}" if t.current is not None else "N/A"
                        temp = f"{t.temperature:.1f}" if t.temperature is not None else "N/A"
                        moving = "Y" if t.moving else "N"
                        err = str(t.error)
                        rows.append([format_motor_id(mid), pos, vel, curr, temp, moving, err])

                    table_str = render_table(headers, rows)
                    output = f"设备: {robot.name} ({robot.id})  bus: {conn_name}  接口: {conn.interface}  mode: raw\n\n{table_str}\n"
                    line_count = output.count("\n")

                    if first_frame:
                        sys.stdout.write(output)
                        sys.stdout.flush()
                        first_frame = False
                        prev_lines = line_count
                    else:
                        sys.stdout.write(f"\033[{prev_lines}A")
                        sys.stdout.write(output)
                        if line_count < prev_lines:
                            for _ in range(prev_lines - line_count):
                                sys.stdout.write("\033[K\n")
                            sys.stdout.write(f"\033[{prev_lines - line_count}A")
                        sys.stdout.flush()
                        prev_lines = line_count

                    time.sleep(sleep_time)

            except KeyboardInterrupt:
                print("\n已停止（KeyboardInterrupt）。退出并断开 motor bus。")
                return 0

    except Exception as e:
        print(f"运行期间出现错误: {e}")
        return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
