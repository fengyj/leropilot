"""诊断脚本：检查 CAN 总线设备是否被正确发现

用法: uv run python examples/diagnose_can_discovery.py
"""

import logging
import sys

logging.basicConfig(level=logging.DEBUG, format="%(levelname)s - %(name)s - %(message)s")


def main():
    print("=" * 80)
    print("CAN 设备发现诊断")
    print("=" * 80)

    # 1. 检查串口设备
    print("\n[步骤 1] 检查所有串口设备:")
    print("-" * 80)
    try:
        import serial.tools.list_ports

        ports = serial.tools.list_ports.comports()
        print(f"发现 {len(ports)} 个串口设备:\n")

        for port in ports:
            print(f"  端口: {port.device}")
            print(f"  描述: {port.description}")
            print(f"  VID:PID: {port.vid:04X}:{port.pid:04X}" if port.vid and port.pid else "  VID:PID: None")
            print(f"  制造商: {port.manufacturer or 'Unknown'}")
            print(f"  产品: {port.product or 'Unknown'}")
            print(f"  序列号: {port.serial_number or 'Unknown'}")
            print(f"  HWID: {port.hwid}")
            print()

    except Exception as e:
        print(f"❌ 错误: {e}")
        return 1

    # 2. 检查已知的 CAN 设备 VID/PID
    print("\n[步骤 2] 检查是否有已知 CAN 设备:")
    print("-" * 80)

    known_can_devices = {
        (0x0C72, 0x000C): "Peak Systems PCAN-USB",
        (0x0C72, 0x0011): "Peak Systems PCAN-USB Pro FD",
        (0x0BFD, None): "Kvaser CAN",
        (0x1B91, None): "Vector Informatik CAN",
        (0x0CE4, None): "ESD Electronics CAN",
        # 添加更多常见的 USB-CAN 适配器
        (0x1D50, 0x606F): "CANable (candleLight firmware)",
        (0x16D0, 0x0F14): "CANtact",
        (0x1209, 0x0001): "CANable 2.0",
    }

    found_can = False
    for port in ports:
        if port.vid and port.pid:
            key1 = (port.vid, port.pid)
            key2 = (port.vid, None)

            if key1 in known_can_devices:
                print(f"✅ 找到已知 CAN 设备: {known_can_devices[key1]}")
                print(f"   端口: {port.device}")
                print(f"   VID:PID: {port.vid:04X}:{port.pid:04X}")
                found_can = True
            elif key2 in known_can_devices:
                print(f"✅ 找到已知 CAN 设备: {known_can_devices[key2]}")
                print(f"   端口: {port.device}")
                print(f"   VID:PID: {port.vid:04X}:{port.pid:04X}")
                found_can = True

    if not found_can:
        print("⚠️  未找到已知的 CAN 设备")
        print("   你的 USB-CAN 适配器可能使用了不在列表中的 VID/PID")
        print("   请手动检查上面列出的设备，找到你的 CAN 适配器")

    # 3. 测试 python-can 库
    print("\n[步骤 3] 测试 python-can 库:")
    print("-" * 80)
    try:
        import can

        print("✅ python-can 库已安装")
        print(f"   版本: {can.__version__}")

        # 列出可用的接口
        print("\n  可用的 CAN 接口类型:")
        interfaces = can.detect_available_configs()
        if interfaces:
            for config in interfaces[:5]:  # 只显示前5个
                print(f"    - {config}")
        else:
            print("    未检测到任何 CAN 接口配置")

    except ImportError:
        print("❌ python-can 库未安装")
        print("   请运行: uv pip install python-can")
        return 1
    except Exception as e:
        print(f"⚠️  检测可用接口时出错: {e}")

    # 4. 测试特定的 CAN 接口
    print("\n[步骤 4] 尝试连接 CAN 接口:")
    print("-" * 80)

    # 常见的 Windows CAN 接口名称
    test_interfaces = []

    # PCAN
    for i in range(1, 9):
        test_interfaces.append(("pcan", f"PCAN_USBBUS{i}"))

    # SLCAN (如果找到了串口设备)
    for port in ports:
        if port.vid and port.pid:
            test_interfaces.append(("slcan", port.device))

    # socketcan (Windows 可能不支持,但试试)
    test_interfaces.append(("socketcan", "can0"))

    successful_interfaces = []

    for bustype, channel in test_interfaces[:10]:  # 限制测试数量
        try:
            print(f"  测试 {bustype}:{channel}... ", end="")
            bus = can.interface.Bus(channel=channel, bustype=bustype, bitrate=1000000)
            print("✅ 成功!")
            successful_interfaces.append((bustype, channel))
            bus.shutdown()
        except Exception as e:
            print(f"❌ 失败: {e}")

    # 5. 测试平台适配器
    print("\n[步骤 5] 测试平台适配器 CAN 发现:")
    print("-" * 80)
    try:
        from leropilot.services.hardware.platform_adapter import PlatformAdapter

        adapter = PlatformAdapter()
        can_interfaces = adapter.discover_can_interfaces()

        print(f"平台适配器发现了 {len(can_interfaces)} 个 CAN 接口:\n")
        for iface in can_interfaces:
            print(f"  接口: {iface.interface}")
            print(f"  制造商: {iface.manufacturer}")
            print(f"  产品: {iface.product}")
            print(f"  VID:PID: {iface.vid}:{iface.pid}")
            print(f"  序列号: {iface.serial_number}")
            print()

    except Exception as e:
        print(f"❌ 错误: {e}")
        import traceback

        traceback.print_exc()

    # 6. 测试设备发现
    print("\n[步骤 6] 测试完整的设备发现流程:")
    print("-" * 80)
    try:
        from leropilot.services.hardware.robots.manager import get_robot_manager

        rm = get_robot_manager()
        pending = rm.get_pending_devices()

        print(f"发现了 {len(pending)} 个待处理设备:\n")
        for device in pending:
            print(f"  设备 ID: {device.id}")
            print(f"  名称: {device.name}")
            print(f"  状态: {device.status}")
            print(f"  电机总线连接: {len(device.motor_bus_connections or {})}")
            print()

    except Exception as e:
        print(f"❌ 错误: {e}")
        import traceback

        traceback.print_exc()

    # 总结
    print("\n" + "=" * 80)
    print("诊断总结:")
    print("=" * 80)

    if successful_interfaces:
        print(f"✅ 找到 {len(successful_interfaces)} 个可用的 CAN 接口:")
        for bustype, channel in successful_interfaces:
            print(f"   - {bustype}:{channel}")
        print("\n建议: 手动测试这些接口是否能扫描到 Damiao 电机")
    else:
        print("❌ 未找到任何可用的 CAN 接口")
        print("\n可能的原因:")
        print("   1. CAN 适配器驱动未正确安装")
        print("   2. CAN 适配器未被识别（VID/PID 不在已知列表）")
        print("   3. 权限问题（尝试以管理员身份运行）")
        print("   4. CAN 适配器硬件故障")

    return 0


if __name__ == "__main__":
    sys.exit(main())
