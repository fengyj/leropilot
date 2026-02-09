"""测试 Damiao 电机扫描

用法: uv run python examples/test_damiao_scan.py
"""

import logging
import sys
import time

# 配置日志
logging.basicConfig(level=logging.DEBUG, format="%(levelname)s - %(name)s - %(message)s")


# 添加过滤器来排除 CAN bus 警告噪音
class CanWarningFilter(logging.Filter):
    def filter(self, record):
        # 排除特定的 CAN bus 警告
        if "Bus error" in record.getMessage() and "warning" in record.getMessage():
            return False
        if "PcanBus was not properly shut down" in record.getMessage():
            return False
        return True


# 应用过滤器到 can.pcan logger
can_logger = logging.getLogger("can.pcan")
can_logger.addFilter(CanWarningFilter())


def test_can_interface_raw(bustype: str, channel: str, baudrate: int, motor_ids: list[int] = None) -> bool:
    """使用原始 python-can 测试接口"""
    import can

    if motor_ids is None:
        motor_ids = list(range(1, 21))  # 默认测试 ID 1-20

    print(f"\n测试 {bustype}:{channel} @ {baudrate} bps (原始 CAN)")
    print("-" * 60)

    try:
        bus = can.interface.Bus(channel=channel, bustype=bustype, bitrate=baudrate)
        print("[OK] CAN 总线已打开")

        # 发送测试消息到多个电机 ID
        print(f"  发送测试消息到电机 ID {motor_ids[:5]}{'...' if len(motor_ids) > 5 else ''}...")

        for test_motor_id in motor_ids[:5]:  # 只测试前 5 个 ID 避免太慢
            msg = can.Message(
                arbitration_id=test_motor_id,
                data=[0x00] * 8,  # 读取电机状态命令
                is_extended_id=False,
            )
            bus.send(msg, timeout=0.5)

        print("  [OK] 消息已发送")

        # 等待响应
        print("  等待响应 (2秒)...")
        start_time = time.time()
        msg_count = 0
        received_ids = set()

        while time.time() - start_time < 2.0:
            msg = bus.recv(timeout=0.1)
            if msg:
                msg_count += 1
                received_ids.add(msg.arbitration_id)
                print(f"  [MSG] 收到消息: ID={msg.arbitration_id:04X} ({msg.arbitration_id}), 数据={msg.data.hex()}")

        if msg_count > 0:
            print(f"  [OK] 收到 {msg_count} 条消息，来自 {len(received_ids)} 个不同 ID: {sorted(received_ids)}")
            bus.shutdown()
            return True
        else:
            print("  [WARN] 未收到响应")
            bus.shutdown()
            return False

    except Exception as e:
        print(f"  [ERROR] 错误: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_damiao_motor_bus(interface: str, baudrate: int, motor_ids: list[int] = None) -> list[int]:
    """使用 DamiaoMotorBus 测试扫描电机"""
    from leropilot.services.hardware.motor_buses.damiao_motor_bus import DamiaoMotorBus

    if motor_ids is None:
        motor_ids = list(range(1, 21))  # 默认扫描 ID 1-20

    print(f"\n测试 {interface} @ {baudrate} bps (DamiaoMotorBus)")
    print("-" * 60)

    try:
        print("  创建 DamiaoMotorBus...")
        bus = DamiaoMotorBus(interface=interface, bitrate=baudrate)

        print("  连接到总线...")
        bus.connect()
        print("  [OK] 已连接")

        print(f"  扫描电机 (ID {motor_ids[0]}-{motor_ids[-1]})...")
        found_motors_dict = bus.scan_motors(id_range=motor_ids)

        if found_motors_dict:
            found_ids = [mid[0] for mid in found_motors_dict.keys()]
            print(f"  [OK] 找到 {len(found_motors_dict)} 个电机: {found_ids}")
            for motor_id, model_info in found_motors_dict.items():
                print(f"     - ID {motor_id}: {model_info.model}")
            bus.disconnect()
            return found_ids
        else:
            print("  [WARN] 未找到电机")
            bus.disconnect()
            return []

    except Exception as e:
        print(f"  ❌ 错误: {e}")
        import traceback

        traceback.print_exc()
        return []


def test_discovery_service():
    """测试完整的设备发现服务"""
    from leropilot.services.hardware.robots.manager import get_robot_manager

    print("\n测试设备发现服务")
    print("=" * 80)

    try:
        rm = get_robot_manager()

        print("调用 get_pending_devices()...")
        pending = rm.get_pending_devices()

        print(f"\n发现了 {len(pending)} 个待处理设备:\n")

        for device in pending:
            print(f"  设备: {device.name} (ID: {device.id})")
            print(f"  状态: {device.status}")

            if device.motor_bus_connections:
                print("  电机总线连接:")
                for bus_id, bus_info in device.motor_bus_connections.items():
                    print(f"    - {bus_id}: {bus_info}")
            else:
                print("  [WARN] 无电机总线连接")
            print()

        return len(pending) > 0

    except Exception as e:
        print(f"[ERROR] 错误: {e}")
        import traceback

        traceback.print_exc()
        return False


def main():
    print("=" * 80)
    print("Damiao 电机扫描测试")
    print("=" * 80)

    # 测试配置
    interfaces = [
        ("pcan", "PCAN_USBBUS1"),
        ("pcan", "PCAN_USBBUS2"),
    ]

    # Damiao 支持的波特率
    baudrates = [1000000, 500000, 250000, 2000000]

    # 要扫描的电机 ID 范围（可以根据实际情况修改）
    motor_ids = list(range(1, 21))  # ID 1-20

    print("\n配置:")
    print(f"  - CAN 接口: {[f'{t}:{c}' for t, c in interfaces]}")
    print(f"  - 波特率: {baudrates}")
    print(f"  - 电机 ID 范围: {motor_ids[0]}-{motor_ids[-1]}")
    print()

    successful_scans = []

    # 阶段 1: 原始 CAN 测试
    print("\n" + "=" * 80)
    print("阶段 1: 原始 CAN 通信测试")
    print("=" * 80)

    for bustype, channel in interfaces:
        for baudrate in baudrates:
            interface_name = f"{bustype}:{channel}"
            if test_can_interface_raw(bustype, channel, baudrate):
                successful_scans.append((interface_name, baudrate))
                # 如果找到响应，不再测试其他波特率
                print(f"  [INFO] 接口 {interface_name} 在 {baudrate} bps 有响应，跳过其他波特率")
                break

    # 阶段 2: DamiaoMotorBus 测试
    print("\n" + "=" * 80)
    print("阶段 2: DamiaoMotorBus 扫描测试")
    print("=" * 80)

    found_motors = []

    if successful_scans:
        print(f"使用第一个成功的配置进行详细扫描: {successful_scans[0]}")
        interface, baudrate = successful_scans[0]
        motors = test_damiao_motor_bus(interface, baudrate, motor_ids)
        if motors:
            found_motors.extend(motors)
    else:
        print("原始 CAN 测试未找到响应，尝试所有配置...")
        for bustype, channel in interfaces:
            interface_name = f"{bustype}:{channel}"
            for baudrate in baudrates:
                motors = test_damiao_motor_bus(interface_name, baudrate, motor_ids)
                if motors:
                    found_motors.extend(motors)
                    successful_scans.append((interface_name, baudrate))
                    break
            if found_motors:
                break

    # 阶段 3: 设备发现服务测试
    print("\n" + "=" * 80)
    print("阶段 3: 设备发现服务测试")
    print("=" * 80)

    discovery_success = test_discovery_service()

    # 总结
    print("\n" + "=" * 80)
    print("测试总结")
    print("=" * 80)

    if successful_scans:
        print(f"\n[OK] 找到 {len(successful_scans)} 个可工作的 CAN 配置:")
        for interface, baudrate in successful_scans:
            print(f"   - {interface} @ {baudrate} bps")
    else:
        print("\n[FAIL] 未找到任何可工作的 CAN 配置")

    if found_motors:
        print(f"\n[OK] 扫描到 {len(found_motors)} 个 Damiao 电机: {found_motors}")
    else:
        print("\n[WARN] 未扫描到任何 Damiao 电机")

    if discovery_success:
        print("\n[OK] 设备发现服务正常工作")
    else:
        print("\n[FAIL] 设备发现服务未找到设备")

    # 诊断建议
    print("\n" + "=" * 80)
    print("诊断建议")
    print("=" * 80)

    if not successful_scans:
        print("\n[FAIL] CAN 总线无响应，可能原因:")
        print("   1. 电机未上电")
        print("   2. CAN 总线接线错误（CAN_H/CAN_L 接反或未连接）")
        print("   3. 终端电阻未正确配置")
        print("   4. 波特率不匹配（尝试检查电机默认波特率）")
        print("   5. CAN 适配器驱动问题")

    elif not found_motors:
        print("\n[WARN] CAN 总线有响应但未识别到电机，可能原因:")
        print(f"   1. 电机 ID 不在 {motor_ids[0]}-{motor_ids[-1]} 范围")
        print("      （修改脚本中的 motor_ids 变量以扫描其他 ID）")
        print("   2. 电机协议版本不匹配")
        print("   3. 总线上有其他设备干扰")
        print("   4. 电机固件问题")

    elif not discovery_success:
        print("\n[WARN] 电机扫描成功但设备发现失败，可能原因:")
        print("   1. 发现服务配置问题")
        print("   2. 接口名称格式不匹配")
        print("   3. 发现逻辑 bug")
        print("\n请检查以下日志中的错误信息")

    else:
        print("\n[OK] 所有测试通过！系统工作正常。")
        print("\n如果 monitor_motor_telemetry.py 仍然无法工作，请:")
        print("   1. 检查该脚本的配置")
        print("   2. 确认电机 ID 和总线配置正确")
        print("   3. 查看完整的错误日志")

    return 0 if (successful_scans and found_motors and discovery_success) else 1


if __name__ == "__main__":
    sys.exit(main())
