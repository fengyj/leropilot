"""直接测试特定 Damiao 电机 ID

用法: uv run python examples/test_damiao_direct.py [motor_id]
示例: uv run python examples/test_damiao_direct.py 3
"""

import logging
import sys
import time

# 设置详细日志
logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")


def test_motor_id(motor_id: int, interface: str = "pcan:PCAN_USBBUS2", bitrate: int = 1000000):
    """直接测试特定电机 ID"""
    import can

    from leropilot.services.hardware.motor_drivers.damiao.tables import DamiaoConstants

    print("=" * 80)
    print(f"直接测试 Damiao 电机 ID {motor_id}")
    print("=" * 80)
    print(f"接口: {interface}")
    print(f"波特率: {bitrate}")
    print()

    # 解析接口
    bustype, channel = interface.split(":", 1)

    # 连接 CAN 总线
    print("步骤 1: 连接 CAN 总线...")
    try:
        bus = can.interface.Bus(channel=channel, bustype=bustype, bitrate=bitrate)
        print("✅ CAN 总线已连接")
    except Exception as e:
        print(f"❌ 连接失败: {e}")
        return False

    # 发送 REFRESH 命令
    print(f"\n步骤 2: 发送 REFRESH 命令到电机 ID {motor_id}...")

    # 构造 refresh 数据
    refresh_data = bytes([motor_id & 0xFF, (motor_id >> 8) & 0xFF, DamiaoConstants.CMD_REFRESH, 0, 0, 0, 0, 0])

    print(f"  数据: {refresh_data.hex()}")
    print(f"  发送到 arbitration_id: 0x{DamiaoConstants.PARAM_ID:03X} (PARAM_ID)")

    try:
        msg = can.Message(arbitration_id=DamiaoConstants.PARAM_ID, data=refresh_data, is_extended_id=False)
        bus.send(msg)
        print("✅ 命令已发送")
    except Exception as e:
        print(f"❌ 发送失败: {e}")
        bus.shutdown()
        return False

    # 等待响应
    print("\n步骤 3: 等待响应 (5秒)...")
    print("  期望:")
    print(f"    - arbitration_id 可能是 {motor_id} (相同 ID)")
    print("    - 或者其他 ID (接收 ID 不同)")
    print(f"    - data[0] 应该是 {motor_id & 0xFF} (0x{motor_id:02X})")
    print()

    start_time = time.time()
    responses = []

    while time.time() - start_time < 5.0:
        msg = bus.recv(timeout=0.1)
        if msg:
            responses.append(msg)
            print("  📨 收到消息:")
            print(f"     arbitration_id: 0x{msg.arbitration_id:03X} ({msg.arbitration_id})")
            print(f"     data: {msg.data.hex()}")
            if len(msg.data) >= 1:
                print(f"     data[0]: 0x{msg.data[0]:02X} ({msg.data[0]})")
                if (msg.data[0] & 0xFF) == (motor_id & 0xFF):
                    print(f"     ✅ data[0] 匹配电机 ID {motor_id}")
                else:
                    print(f"     ⚠️  data[0] 不匹配 (期望: {motor_id})")
            print()

    bus.shutdown()

    # 总结
    print("=" * 80)
    print("测试结果")
    print("=" * 80)

    if responses:
        print(f"✅ 收到 {len(responses)} 条响应")

        # 检查是否有匹配的响应
        matching = [msg for msg in responses if len(msg.data) >= 1 and (msg.data[0] & 0xFF) == (motor_id & 0xFF)]

        if matching:
            print(f"✅ 其中 {len(matching)} 条匹配电机 ID {motor_id}")
            print("\n匹配的响应:")
            for msg in matching:
                print(f"  - arbitration_id: 0x{msg.arbitration_id:03X}")
                print(f"    data: {msg.data.hex()}")
            return True
        else:
            print(f"⚠️  没有响应匹配电机 ID {motor_id}")
            print("\n可能的原因:")
            print(f"  1. 电机 ID 不是 {motor_id}")
            print("  2. 电机未上电")
            print("  3. 电机损坏")
            return False
    else:
        print("❌ 未收到任何响应")
        print("\n可能的原因:")
        print("  1. 电机未连接或未上电")
        print("  2. CAN 总线接线错误")
        print("  3. 波特率不匹配")
        print("  4. 终端电阻配置错误")
        return False


def main():
    # 解析命令行参数
    if len(sys.argv) > 1:
        try:
            motor_id = int(sys.argv[1])
        except ValueError:
            print(f"错误: 无效的电机 ID '{sys.argv[1]}'")
            print(f"用法: {sys.argv[0]} [motor_id]")
            print(f"示例: {sys.argv[0]} 3")
            return 1
    else:
        motor_id = 3  # 默认测试 ID 3

    interface = "pcan:PCAN_USBBUS2"
    bitrate = 1000000

    # 也可以通过命令行参数指定接口
    if len(sys.argv) > 2:
        interface = sys.argv[2]
    if len(sys.argv) > 3:
        bitrate = int(sys.argv[3])

    success = test_motor_id(motor_id, interface, bitrate)

    if not success:
        print("\n建议:")
        print(f"  1. 确认电机 ID 是否真的是 {motor_id} (可能需要查看电机配置)")
        print("  2. 尝试扫描多个 ID: uv run python examples/test_damiao_direct.py 1")
        print("  3. 检查硬件连接和供电")
        print("  4. 尝试其他波特率: uv run python examples/test_damiao_direct.py 3 pcan:PCAN_USBBUS2 500000")

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
