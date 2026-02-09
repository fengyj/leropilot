# CAN 总线错误诊断与解决方案

## 错误描述

```
Bus error: an error counter reached the 'heavy'/'warning' limit
```

这表明 CAN 总线的 **发送错误计数器 (TEC)** 或 **接收错误计数器 (REC)** 超过了警告阈值（通常是 96）。

## CAN 总线错误等级

CAN 控制器有三个错误状态：

1. **Error Active** (正常): TEC < 96, REC < 96
2. **Error Passive** (警告): TEC ≥ 96 或 REC ≥ 96  ← **当前状态**
3. **Bus Off** (离线): TEC > 255

## 常见原因及解决方案

### 1. 终端电阻问题 ⚡ (最常见)

**问题**: CAN 总线需要在两端各有一个 120Ω 终端电阻，总阻抗应为 60Ω。

**诊断**:
```bash
# 关闭所有设备电源，用万用表测量 CAN_H 和 CAN_L 之间的电阻
# 应该读数约为 60Ω (两个 120Ω 电阻并联)
```

**解决方案**:
- ✅ 在总线**两端**各添加一个 120Ω 电阻
- ❌ 不要在中间设备上添加终端电阻
- ❌ 不要遗漏任何一端的电阻
- ❌ 不要使用错误阻值（如 100Ω 或 150Ω）

**正确接线示例**:
```
[USB-CAN] ---120Ω--- [CANH/CANL] --- [电机1] --- [电机2] --- ... --- [电机N] ---120Ω---
   终端1                                                                            终端2
```

### 2. 波特率不匹配 🔧

**问题**: 主机和电机的波特率设置不一致。

**Damiao 电机默认波特率**: 1 Mbps (1000000)

**检查代码**:
```python
# 检查 src/leropilot/services/hardware/motor_drivers/damiao/tables.py
DEFAULT_BAUDRATE = 1000000  # 必须匹配电机设置
```

**解决方案**:
```bash
# Windows: 检查 CAN 适配器配置
# 在设备管理器中查看 USB-CAN 适配器设置

# Linux: 设置 CAN 接口波特率
sudo ip link set can0 type can bitrate 1000000
sudo ip link set can0 up
```

### 3. 线缆质量与长度 📏

**问题**: 线缆太长、质量差或连接松动。

**CAN 总线长度限制**:
| 波特率 | 最大长度 |
|--------|----------|
| 1 Mbps | 40 m     |
| 500 kbps | 100 m   |
| 125 kbps | 500 m   |

**解决方案**:
- ✅ 使用**双绞线**（推荐 CAT5/CAT6 网线）
- ✅ 确保连接牢固，检查接头是否松动
- ✅ 保持线缆尽可能短
- ❌ 避免使用普通单股线
- ❌ 避免长距离使用细线（至少 22 AWG）

### 4. 电源问题 ⚡

**问题**: 电源不稳定或接地不良。

**检查项**:
- 电机供电电压是否在规格范围内（Damiao: 24V-48V）
- 是否有电压跌落（启动瞬间）
- 地线是否连接良好

**解决方案**:
```
- 使用足够功率的电源（至少留 30% 余量）
- 确保所有设备共地
- 添加电源滤波电容（推荐：1000μF 电解 + 0.1μF 陶瓷）
```

### 5. 总线负载过高 📊

**问题**: 发送消息过于频繁或设备过多。

**诊断**:
```python
# 检查发送频率
# 正常的控制循环频率: 100-1000 Hz
# 如果超过 1000 Hz，可能需要降低频率
```

**解决方案**:
- 减少轮询频率
- 使用批量读写而不是逐个电机操作
- 限制同时通信的电机数量（建议 ≤ 8 个）

### 6. 电气干扰 📡

**问题**: 电磁干扰影响信号完整性。

**解决方案**:
- ✅ 使用**屏蔽双绞线**
- ✅ 屏蔽层正确接地（一端接地）
- ✅ CAN 线与电源线分开走线（至少 10cm）
- ❌ 避免与电机电源线平行走线
- ❌ 避免线缆成环

### 7. CAN 适配器质量 🔌

**问题**: 低质量的 USB-CAN 适配器。

**推荐设备**:
- PEAK PCAN-USB
- Kvaser Leaf Light
- CANable (开源方案)

**不推荐**: 廉价的无品牌适配器可能不支持错误恢复

## 诊断步骤

### 第一步：检查硬件连接

```bash
# 1. 关闭电源
# 2. 检查接线：
#    - CAN_H 接 CAN_H
#    - CAN_L 接 CAN_L
#    - 地线连接
# 3. 测量终端电阻（应为 60Ω）
# 4. 检查线缆是否有损坏
```

### 第二步：验证波特率

```bash
# Linux 查看 CAN 状态
ip -details -statistics link show can0

# 应该显示:
# bitrate 1000000
# sample-point 0.875
# tq 62 prop-seg 6 phase-seg1 7 phase-seg2 2 sjw 1
```

### 第三步：逐个添加设备

```python
# 从单个电机开始测试
# 如果单个电机正常，逐个添加更多电机
# 找出导致错误的设备数量阈值
```

### 第四步：监控错误计数器

```python
# 创建诊断脚本
import can

bus = can.interface.Bus(channel='can0', bustype='socketcan')

while True:
    # 读取错误计数器状态
    state = bus.state
    print(f"Bus state: {state}")
    
    # 如果有错误帧，打印出来
    msg = bus.recv(timeout=0.1)
    if msg and msg.is_error_frame:
        print(f"Error frame: {msg}")
```

## 代码层面的改进

### 1. 添加错误计数器监控

```python
# 在 damiao/drivers.py 中添加
def check_bus_health(self) -> dict[str, int]:
    """检查 CAN 总线健康状态"""
    if hasattr(self.bus, 'state'):
        return {
            'state': str(self.bus.state),
            'tx_errors': getattr(self.bus, 'tx_error_counter', -1),
            'rx_errors': getattr(self.bus, 'rx_error_counter', -1),
        }
    return {}
```

### 2. 实现自动错误恢复

```python
# 检测到错误时自动重启总线
def auto_recover_from_bus_error(self):
    """自动从总线错误中恢复"""
    logger.warning("Attempting bus error recovery...")
    try:
        self.disconnect()
        time.sleep(0.5)  # 等待总线稳定
        self.connect()
        logger.info("Bus recovery successful")
        return True
    except Exception as e:
        logger.error(f"Bus recovery failed: {e}")
        return False
```

### 3. 降低通信频率

```python
# 添加发送间隔
import time

class DamiaoDriver:
    def __init__(self, ...):
        self._last_send_time = 0
        self._min_send_interval = 0.001  # 1ms 最小间隔
    
    def _throttled_send(self, msg):
        """限流发送，避免总线过载"""
        now = time.time()
        elapsed = now - self._last_send_time
        if elapsed < self._min_send_interval:
            time.sleep(self._min_send_interval - elapsed)
        
        self.bus.send(msg)
        self._last_send_time = time.time()
```

## 快速检查清单

- [ ] 两端都有 120Ω 终端电阻
- [ ] 波特率设置为 1000000 (1 Mbps)
- [ ] 使用双绞线（推荐屏蔽）
- [ ] 线缆长度 < 40m
- [ ] 电源稳定且共地
- [ ] CAN_H 和 CAN_L 没有接反
- [ ] 没有松动的连接
- [ ] CAN 适配器驱动已正确安装
- [ ] 只在总线两端有终端电阻（不是每个设备）

## 使用诊断工具

### Linux: candump 和 cansend

```bash
# 安装 can-utils
sudo apt-get install can-utils

# 监控总线流量
candump can0

# 查看错误统计
ip -s link show can0

# 发送测试消息
cansend can0 123#DEADBEEF
```

### Windows: PCAN-View

1. 下载 PEAK-System 的 PCAN-View
2. 连接后查看 "Bus Load" 和 "Error Frames"
3. 正常情况下错误帧应该是 0

## 预防措施

1. **设计时**:
   - 计算总线负载（< 70% 为安全）
   - 预留足够的电源裕量
   - 使用质量好的连接器

2. **安装时**:
   - 先测量终端电阻
   - 使用线缆测试仪检查连通性
   - 标记 CAN_H 和 CAN_L

3. **运行时**:
   - 监控错误计数器
   - 记录总线负载
   - 定期检查连接

## 参考资料

- [CAN Bus Termination - TI Application Note](https://www.ti.com/lit/an/slla270/slla270.pdf)
- [CAN Error Handling - Kvaser](https://www.kvaser.com/about-can/can-standards/can-error-handling/)
- [ISO 11898 CAN Specification](https://www.iso.org/standard/63648.html)

## 总结

90% 的 CAN 总线错误是由以下原因导致：

1. **缺少或错误的终端电阻** (50%)
2. **波特率不匹配** (20%)
3. **线缆质量或长度问题** (15%)
4. **接线错误或接触不良** (5%)

**优先检查**: 终端电阻 → 波特率 → 线缆质量 → 接线
