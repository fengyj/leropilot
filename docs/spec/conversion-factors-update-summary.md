# Conversion Factors Update Summary

## 完成日期
2026-01-27

## 更新内容

已为所有电机驱动的 `MotorModelInfo` 实例添加物理单位转换系数。这些转换系数用于新的标准化单位API (`bulk_write_values` / `bulk_read_values`)。

## 转换系数字段

在 `MotorModelInfo` 中新增的字段：

- `current_unit_ma_per_bit: float | None` - 电流转换系数（毫安/寄存器单位）
- `voltage_unit_v_per_bit: float | None` - 电压转换系数（伏特/寄存器单位）
- `temperature_unit_c_per_bit: float | None` - 温度转换系数（摄氏度/寄存器单位）
- `acceleration_unit_rad_s2_per_bit: float | None` - 加速度转换系数（弧度每平方秒/寄存器单位）

## 各品牌电机转换系数

### Dynamixel电机

**X系列（XM430, XM540, XL430, XC430, XC330）:**
- Current: 2.69 mA/unit
- Voltage: 0.1 V/unit
- Temperature: 1.0 °C/unit
- Acceleration: 0.3738 rad/s²/unit

**XL330系列:**
- Current: 3.36 mA/unit（注意：与其他X系列不同）
- Voltage: 0.1 V/unit
- Temperature: 1.0 °C/unit
- Acceleration: 0.3738 rad/s²/unit

**MX系列（Protocol 2.0）:**
- Current: 2.69 mA/unit
- Voltage: 0.1 V/unit
- Temperature: 1.0 °C/unit
- Acceleration: 0.3738 rad/s²/unit

### Feetech电机

**所有STS/SCS系列:**
- Current: 6.5 mA/unit
- Voltage: 0.1 V/unit
- Temperature: 1.0 °C/unit
- Acceleration: None（Feetech电机通常不支持加速度寄存器）

### Damiao电机

**所有DM系列（通过CAN总线）:**
- Current: 1000.0 mA/unit（1 A/unit，CAN协议使用安培）
- Voltage: 1.0 V/unit（直接使用伏特）
- Temperature: 1.0 °C/unit（直接使用摄氏度）
- Acceleration: None（通常不通过参数寄存器读写）

注意：Damiao电机通过CAN总线通信，大部分物理量已经是标准单位，所以转换系数接近1.0。

## API使用示例

### 写入标准单位值

```python
from leropilot.services.hardware.motor_drivers.dynamixel import DynamixelDriver
from leropilot.services.hardware.motor_drivers.dynamixel.tables import select_model_for_number

# 初始化驱动
driver = DynamixelDriver(interface="/dev/ttyUSB0", baud_rate=1000000)

# 获取电机型号信息
motor_models = {
    1: select_model_for_number(1020),  # XM430-W350
    2: select_model_for_number(1190),  # XL330-M077
}

# 写入电流限制（使用标准单位：mA）
current_limits = {
    1: 1000.0,  # 1000mA for motor 1
    2: 800.0,   # 800mA for motor 2
}

success = driver.bulk_write_values(
    motor_values=current_limits,
    motor_models=motor_models,
    register_addr=38,  # Current Limit register
    register_len=2,
    unit_type="current",
)

# 驱动程序自动：
# 1. 根据motor_models查找每个电机的current_unit_ma_per_bit
# 2. 将mA转换为寄存器单位（motor 1: 1000/2.69=371, motor 2: 800/3.36=238）
# 3. 通过单次批量事务写入所有值
```

### 读取标准单位值

```python
# 读取当前电流（使用标准单位：mA）
currents = driver.bulk_read_values(
    motor_models=motor_models,
    register_addr=126,  # Present Current register
    register_len=2,
    unit_type="current",
    signed=True,  # Current can be negative
)

# 返回: {1: 1000.0, 2: -500.0} (单位：mA)
# 驱动程序自动：
# 1. 读取原始寄存器值
# 2. 处理有符号整数（二进制补码）
# 3. 使用每个电机的current_unit_ma_per_bit转换为mA
```

## 更新的文件

### 核心模型
- `src/leropilot/models/hardware.py` - 添加了4个新的转换系数字段到 `MotorModelInfo`

### 电机表定义
- `src/leropilot/services/hardware/motor_drivers/dynamixel/tables.py` - 18个模型实例已更新
- `src/leropilot/services/hardware/motor_drivers/feetech/tables.py` - 10个模型实例已更新
- `src/leropilot/services/hardware/motor_drivers/damiao/tables.py` - 7个模型实例已更新

### API实现
- `src/leropilot/services/hardware/motor_drivers/base.py` - 已包含完整的 `bulk_write_values` / `bulk_read_values` / `_get_conversion_factor` 实现

### 测试/示例
- `examples/hardware/test_conversion_factors.py` - 验证所有转换系数的测试脚本

## 设计优势

### 旧API（需要手动查找转换系数）
```python
# 需要用户手动查找和提供转换系数
from leropilot.services.hardware.motor_drivers.dynamixel.tables import DynamixelUnits

driver.bulk_write_values(
    motor_values={1: 1000.0, 2: 800.0},
    register_addr=38,
    register_len=2,
    conversion_factor=DynamixelUnits.CURRENT_MA_PER_UNIT,  # 手动查找
)
# 问题：无法处理混合型号（XM430和XL330的转换系数不同）
```

### 新API（自动查找转换系数）
```python
# 驱动程序自动从motor_models中查找转换系数
driver.bulk_write_values(
    motor_values={1: 1000.0, 2: 800.0},
    motor_models={1: xm430_model, 2: xl330_model},
    register_addr=38,
    register_len=2,
    unit_type="current",  # 指定单位类型
)
# 优势：
# 1. 自动为每个电机使用正确的转换系数
# 2. 支持混合电机型号
# 3. 类型安全（unit_type是枚举）
# 4. 减少用户错误（不会用错转换系数）
```

## 验证

运行测试脚本验证所有转换系数：

```bash
uv run python examples/hardware/test_conversion_factors.py
```

输出显示：
- ✅ 18个Dynamixel模型全部填充了转换系数
- ✅ 10个Feetech模型全部填充了转换系数
- ✅ 7个Damiao模型全部填充了转换系数
- ✅ 无警告或错误

## 后续工作

根据对话summary，还有以下待办事项：

1. **保持telemetry返回原始单位（已确认）**
   - `read_telemetry` 和 `bulk_read_telemetry` 保持position和velocity返回原始值
   - 其他值（current, voltage, temperature）已经返回标准单位

2. **更新高级API方法（可选）**
   - 考虑更新 `bulk_write_current_limit`、`bulk_write_velocity_limit` 等高级方法
   - 让它们使用新的 `bulk_write_values` API内部实现
   - 接受 `motor_models` 参数而不是硬编码的转换系数

3. **文档更新（可选）**
   - 在用户文档中说明新的标准化单位API
   - 提供迁移指南（从旧API迁移到新API）

## 技术注意事项

- **Velocity ratio复用**: velocity使用现有的 `velocity_ratio` 字段，不需要新字段
- **None值处理**: acceleration对于某些品牌可以是None（如Feetech、Damiao）
- **单位一致性**: 所有品牌统一使用相同的标准单位（mA, V, °C, rad/s²）
- **向后兼容**: 旧的常量类（DynamixelUnits, FeetechUnits）保留用于向后兼容
