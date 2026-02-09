#!/usr/bin/env python3
"""示例脚本：通过 Damiao MotorBus 控制电机位置或以恒定速度旋转。

用法示例：
  # 控制第一个发现到的 Damiao 电机，以 0.5 rad/s 旋转 5 秒
  python examples/control_damiao_motor.py --interface "pcan:PCAN_USBBUS2" --baud 1000000 --mode velocity --value 0.5 --duration 5

  # 将第一个发现的电机转到 0.78 rad（以默认速度）
  python examples/control_damiao_motor.py --interface "pcan:PCAN_USBBUS2" --baud 1000000 --mode position --value 0.78

注意：Damiao 驱动的底层实现对 position 单位/缩放有历史遗留差异，建议使用 `--position-type raw_in_radian` 明确以弧度为单位。
"""

from __future__ import annotations

import argparse
import sys
import time
from typing import Any

from leropilot.models.hardware import PositionType
from leropilot.services.hardware.motor_buses.motor_bus import MotorBus


def parse_motor_key(s: str) -> Any:
    """Parse motor id argument (int or send:recv).

    Returns int or tuple(int,int).
    """
    if ":" in s or "," in s or " " in s:
        sep = ":" if ":" in s else ("," if "," in s else " ")
        parts = [p for p in s.split(sep) if p]
        if len(parts) != 2:
            raise ValueError("motor id must be single int or two ints separated by ':' or ','")
        return (int(parts[0]), int(parts[1]))
    return int(s)


def find_motor_by_send(discovered: dict, send_id: int):
    """Find a discovered Damiao motor tuple by its send id."""
    for mid in discovered.keys():
        if isinstance(mid, (list, tuple)) and int(mid[0]) == int(send_id):
            return mid
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Control Damiao motor (position or velocity mode)")
    parser.add_argument("--interface", required=True, help='CAN interface, e.g. "pcan:PCAN_USBBUS2"')
    parser.add_argument("--baud", type=int, default=1000000, help="CAN bitrate (default: 1000000)")
    parser.add_argument(
        "--motor", required=False, help="Motor id (send or send:recv). If omitted the first discovered motor is used"
    )

    parser.add_argument("--mode", choices=("position", "velocity"), required=True, help="Control mode")
    parser.add_argument(
        "--value", type=float, required=True, help="Target position (rad for raw_in_radian) or velocity (rad/s)"
    )
    parser.add_argument(
        "--duration", type=float, default=5.0, help="Duration in seconds for velocity mode (default 5s)"
    )
    parser.add_argument(
        "--position-type",
        choices=("raw", "raw_in_radian", "calibrated", "calibrated_in_radian"),
        default="raw_in_radian",
        help="Unit for position mode (default: raw_in_radian)",
    )
    parser.add_argument(
        "--no-confirm", action="store_true", help="Do not prompt for confirmation before enabling torque"
    )
    parser.add_argument("--disable-after", action="store_true", help="Disable torque after operation completes")

    # args = parser.parse_args()

    # Create MotorBus for Damiao
    try:
        mb = MotorBus.create("damiao", "pcan:PCAN_USBBUS2", 1000000)
    except Exception as e:
        print(f"Failed to create MotorBus: {e}")
        return 2

    try:
        with mb:
            # print(f"Connected to motor bus {args.interface} @ {args.baud}")
            mb.connect()
            discovered = mb.scan_motors()
            if not discovered:
                print("未发现任何 Damiao 电机，请检查接口与接线。")
                return 1

            # Choose motor
            target_mid = None
            target_mid = next(iter(discovered.keys()))

            print(f"目标电机: {target_mid} model={discovered[target_mid].model}")

            print("启用扭矩...")
            try:
                mb.set_torque(target_mid, True)
                time.sleep(0.2)  # 等待0.1秒以确保位置命令被处理
            except Exception as e:
                print(f"启用扭矩失败: {e}")
                return 1

            try:
                # Map position-type
                # pt = PositionType.RAW if args.position_type == "raw" else (
                #     PositionType.RAW_IN_RADIAN if args.position_type == "raw_in_radian" else (
                #         PositionType.CALIBRATED if args.position_type == "calibrated" else PositionType.CALIBRATED_IN_RADIAN
                #     )
                # )
                # print(f"设置目标位置: {args.value} ({pt})")
                print(f"当前位置： {mb.get_position(target_mid, position_type=PositionType.RAW_IN_RADIAN):.3f} rad")
                for _ in range(3):
                    position = mb.get_position(target_mid, position_type=PositionType.RAW_IN_RADIAN) 
                    mb.set_goal_position(target_mid, 1.5708 + position, position_type=PositionType.RAW_IN_RADIAN)
                    time.sleep(0.5)
                print("位置命令已发送。")
                time.sleep(1.0)  # 等待一秒以确保位置命令被处理

            finally:
                mb.set_torque(target_mid, False)
    except Exception as e:
        print(f"运行期间出现错误: {e}")
        return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
