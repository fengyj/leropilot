# 批量寄存器初始化示例

## 概述

新增的 `bulk_write_register` 方法允许批量设置多个电机的同一寄存器，用于高效的批量初始化配置。

## 性能优势

| Driver | 实现方式 | 性能 |
|--------|---------|------|
| **Dynamixel** | GroupSyncWrite | 单次总线事务，最优 |
| **Feetech** | scservo_sdk syncWrite | 单次总线事务，最优 |
| **Damiao** | 批处理CAN写入 | 批量发送→批量收集，5-10倍提升 |

---

## API 签名

```python
def bulk_write_register(
    self,
    motor_values: dict[MotorID, int],
    register_addr: int,
    register_len: int,
) -> dict[MotorID, bool]:
    """Write the same register to multiple motors with different values.
    
    Args:
        motor_values: Dict mapping motor_id -> value to write
        register_addr: Register address to write
        register_len: Register length in bytes (1, 2, or 4)
    
    Returns:
        Dict mapping motor_id -> success (bool)
    """
```

---

## 使用示例

### 1. Dynamixel - 批量设置电流限制

```python
from leropilot.services.hardware.motor_drivers.dynamixel import DynamixelDriver
from leropilot.services.hardware.motor_drivers.dynamixel.tables import DynamixelRegisters

driver = DynamixelDriver(interface="COM3", baud_rate=1000000)
driver.connect()

# 为电机 1, 2, 3 设置电流限制为 1000mA
results = driver.bulk_write_register(
    motor_values={1: 1000, 2: 1000, 3: 1000},
    register_addr=DynamixelRegisters.CURRENT_LIMIT[0],  # 38
    register_len=DynamixelRegisters.CURRENT_LIMIT[1],   # 2 bytes
)

# 检查结果
for motor_id, success in results.items():
    print(f"Motor {motor_id}: {'✓' if success else '✗'}")
```

### 2. Dynamixel - 批量设置操作模式

```python
# 设置多个电机为位置控制模式 (Operating Mode = 3)
results = driver.bulk_write_register(
    motor_values={1: 3, 2: 3, 3: 3, 4: 3},
    register_addr=DynamixelRegisters.OPERATING_MODE[0],  # 11
    register_len=DynamixelRegisters.OPERATING_MODE[1],   # 1 byte
)
```

### 3. Dynamixel - 批量设置Drive Mode（反向旋转）

```python
# 为电机 1, 3 设置反向旋转 (Drive Mode bit 0 = 1)
# 电机 2, 4 保持正向 (Drive Mode = 0)
results = driver.bulk_write_register(
    motor_values={1: 1, 2: 0, 3: 1, 4: 0},
    register_addr=DynamixelRegisters.DRIVE_MODE[0],  # 10
    register_len=DynamixelRegisters.DRIVE_MODE[1],   # 1 byte
)
```

### 4. Feetech - 批量设置最大加速度

```python
from leropilot.services.hardware.motor_drivers.feetech import FeetechDriver
from leropilot.services.hardware.motor_drivers.feetech.tables import SCS_STS_Registers

driver = FeetechDriver(interface="COM5", baud_rate=1000000)
driver.connect()

# 为多个电机设置加速度限制
results = driver.bulk_write_register(
    motor_values={1: 254, 2: 254, 3: 254},
    register_addr=SCS_STS_Registers.MAX_ACCELERATION[0],  # 41
    register_len=SCS_STS_Registers.MAX_ACCELERATION[1],   # 1 byte
)
```

### 5. Damiao - 批量设置PID参数（P增益）

```python
from leropilot.services.hardware.motor_drivers.damiao import DamiaoDriver

driver = DamiaoDriver(interface="can0", baud_rate=1000000)
driver.connect()

# 为多个Damiao电机设置P增益为50
# 注意：Damiao使用 (send_id, recv_id) 元组作为motor_id
results = driver.bulk_write_register(
    motor_values={
        (1, 1): 50,
        (2, 2): 50,
        (3, 3): 50,
    },
    register_addr=0x30,  # P gain parameter address
    register_len=2,      # 2 bytes
)
```

---

## 完整的机器人初始化示例

### Dynamixel 机器人初始化配置

```python
from leropilot.services.hardware.motor_drivers.dynamixel import DynamixelDriver
from leropilot.services.hardware.motor_drivers.dynamixel.tables import DynamixelRegisters

def initialize_robot(driver: DynamixelDriver, motor_ids: list[int]):
    """批量初始化机器人所有电机配置"""
    
    # 1. 禁用扭矩（配置前必须禁用）
    driver.bulk_set_torque(motor_ids, enabled=False)
    
    # 2. 设置操作模式为位置控制 (Operating Mode = 3)
    print("Setting operating mode...")
    driver.bulk_write_register(
        {mid: 3 for mid in motor_ids},
        register_addr=DynamixelRegisters.OPERATING_MODE[0],
        register_len=DynamixelRegisters.OPERATING_MODE[1],
    )
    
    # 3. 设置电流限制为1000mA（保护电机）
    print("Setting current limits...")
    driver.bulk_write_register(
        {mid: 1000 for mid in motor_ids},
        register_addr=DynamixelRegisters.CURRENT_LIMIT[0],
        register_len=DynamixelRegisters.CURRENT_LIMIT[1],
    )
    
    # 4. 设置速度限制
    print("Setting velocity limits...")
    driver.bulk_write_register(
        {mid: 200 for mid in motor_ids},
        register_addr=DynamixelRegisters.PROFILE_VELOCITY[0],
        register_len=DynamixelRegisters.PROFILE_VELOCITY[1],
    )
    
    # 5. 配置某些电机反向旋转
    # 假设电机 2, 4 需要反向
    print("Configuring drive modes...")
    drive_modes = {
        1: 0, 2: 1,  # Motor 2 reversed
        3: 0, 4: 1,  # Motor 4 reversed
        5: 0, 6: 0,
    }
    driver.bulk_write_register(
        drive_modes,
        register_addr=DynamixelRegisters.DRIVE_MODE[0],
        register_len=DynamixelRegisters.DRIVE_MODE[1],
    )
    
    # 6. 启用扭矩
    print("Enabling torque...")
    driver.bulk_set_torque(motor_ids, enabled=True)
    
    print("✓ Robot initialization complete!")


# 使用示例
driver = DynamixelDriver(interface="COM3", baud_rate=1000000)
driver.connect()

motor_ids = [1, 2, 3, 4, 5, 6]
initialize_robot(driver, motor_ids)
```

---

## 性能对比

### 传统顺序写入 vs 批量写入

```python
import time

# ❌ 传统方式：顺序写入（慢）
start = time.time()
for motor_id in range(1, 11):  # 10个电机
    driver._write_register(motor_id, register_addr=38, value=1000, length=2)
    # 每次写入 ~5-10ms
elapsed_old = time.time() - start
# 预期耗时: 50-100ms

# ✅ 批量写入（快）
start = time.time()
driver.bulk_write_register(
    {mid: 1000 for mid in range(1, 11)},
    register_addr=38,
    register_len=2,
)
elapsed_new = time.time() - start
# 预期耗时: ~5-15ms（单次总线事务）

print(f"性能提升: {elapsed_old / elapsed_new:.1f}x")
# 输出: 性能提升: 5.0-10.0x
```

---

## 注意事项

### 1. Damiao 协议限制
- Damiao CAN协议对寄存器写入支持有限
- 不是所有参数都可通过CAN总线配置
- 某些参数可能需要专用配置工具

### 2. 配置前禁用扭矩
大多数电机在修改操作模式等配置时需要先禁用扭矩：

```python
# 1. 禁用扭矩
driver.bulk_set_torque(motor_ids, enabled=False)

# 2. 修改配置
driver.bulk_write_register(...)

# 3. 重新启用扭矩
driver.bulk_set_torque(motor_ids, enabled=True)
```

### 3. 错误处理
```python
results = driver.bulk_write_register(motor_values, addr, length)

# 检查失败的电机
failed_motors = [mid for mid, success in results.items() if not success]
if failed_motors:
    print(f"Warning: Failed to configure motors: {failed_motors}")
```

---

## 相关API

- `bulk_set_torque()` - 批量启用/禁用扭矩
- `bulk_set_position()` - 批量设置目标位置
- `bulk_read_telemetry()` - 批量读取遥测数据
- `_write_register()` - 单个电机写寄存器（内部方法）

---

## 总结

`bulk_write_register` 方法提供了高效的批量配置能力，特别适合：

✅ 机器人启动时的批量初始化  
✅ 运行时批量调整PID参数  
✅ 批量设置安全限制（电流、速度、位置范围）  
✅ 批量配置操作模式和驱动模式  

通过使用批量操作，可以将配置时间从数百毫秒缩短到几十毫秒，显著提升系统响应速度和用户体验。
