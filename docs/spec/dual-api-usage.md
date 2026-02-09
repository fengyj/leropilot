# Dual API Design: Physical Units vs Raw Register Values

This document explains the three-layer API design for motor drivers and when to use each.

## Overview

All motor drivers (`DynamixelDriver`, `FeetechDriver`, `DamiaoCAN_Driver`) provide **three APIs**:

1. **High-level API** (recommended): Specific methods for common parameters (mA, rad/s, °C)
2. **Standardized Units API** (flexible): Generic methods for any register with standard units
3. **Low-level API** (advanced): Raw register access with integer values

### Standard Physical Units

All motor drivers use consistent physical units across the codebase:

| Quantity | Standard Unit | Symbol |
|----------|---------------|--------|
| Position | radians | rad |
| Velocity | radians per second | rad/s |
| Acceleration | radians per second squared | rad/s² |
| Current | milliamperes | mA |
| Voltage | volts | V |
| Temperature | degrees Celsius | °C |
| Torque | Newton-meters | N·m |
| Force | Newtons | N |
| Time | seconds | s |

**Position is always in radians (rad)**, not encoder units or degrees.

---

## API Layers Explained

### Layer 1: High-Level API (Specific Methods)

**Best for:** Common configuration parameters

✅ Use when setting current limits, velocity limits, temperature limits, operating modes

```python
# Dynamixel
driver.bulk_write_current_limit({1: 1000, 2: 800})      # mA
driver.bulk_write_velocity_limit({1: 2.0, 2: 1.5})      # rad/s
driver.bulk_write_temperature_limit({1: 70, 2: 65})     # °C

# Feetech
driver.bulk_write_current_limit({1: 500, 2: 400})       # mA
driver.bulk_write_velocity_limit({1: 1.5, 2: 1.0})      # rad/s
driver.bulk_write_temperature_limit({1: 65, 2: 60})     # °C
```

**Pros:**
- Most concise and readable
- Self-documenting method names
- No need to look up register addresses

**Cons:**
- Limited to predefined common parameters
- Write-only (no read support yet)

### Layer 2: Standardized Units API (Generic Methods)

**Best for:** Any register that needs unit conversion

✅ Use when reading/writing registers with physical units beyond common parameters

```python
# WRITE: Standard units → Register
driver.bulk_write_values(
    motor_values={1: 1000.0, 2: 800.0},  # Standard unit: mA
    register_addr=38,                     # Current limit register
    register_len=2,                       # 16-bit
    conversion_factor=2.69,               # Dynamixel: 2.69 mA/unit
)

# READ: Register → Standard units
currents = driver.bulk_read_values(
    motor_ids=[1, 2, 3],
    register_addr=126,                    # Present current register
    register_len=2,
    conversion_factor=2.69,
    signed=True,                          # Support negative values
)
# Returns: {1: 1000.0, 2: -500.0, 3: 0.0} in mA
```

**Pros:**
- Works for **any register** with unit conversion
- Both **read and write** support
- Handles signed/unsigned values automatically
- Consistent API across all drivers

**Cons:**
- More verbose than Layer 1
- Need to know register address and conversion factor

### Layer 3: Low-Level API (Raw Register Access)

**Best for:** Direct hardware control, debugging, pre-computed values

✅ Use when you need exact register values or maximum performance

```python
# WRITE: Raw register values (no conversion)
driver.bulk_write_register(
    motor_values={1: 372, 2: 297},  # Raw register values
    register_addr=38,
    register_len=2,
)

# READ: Raw register values (no conversion)
raw_values = driver.bulk_read_register(
    motor_ids=[1, 2, 3],
    register_addr=38,
    register_len=2,
)
# Returns: {1: 372, 2: 297, 3: 446} (raw units)
```

**Pros:**
- No conversion overhead
- Exact control over register values
- Useful for debugging hardware issues

**Cons:**
- Manual unit conversion required
- Error-prone (magic numbers)
- Model-specific register values

---

## When to Use Each Layer

| Scenario | Layer 1 | Layer 2 | Layer 3 |
|----------|---------|---------|---------|
| Setting current limits | ✅ | ✅ | ⚠️ |
| Setting velocity limits | ✅ | ✅ | ⚠️ |
| Reading present current | ❌ | ✅ | ⚠️ |
| Reading custom register | ❌ | ✅ | ⚠️ |
| Writing PID gains | ❌ | ✅ | ⚠️ |
| Pre-computed control loop | ❌ | ❌ | ✅ |
| Hardware debugging | ❌ | ❌ | ✅ |

**Legend:**
- ✅ Recommended
- ⚠️ Advanced use only
- ❌ Not supported

✅ **You want intuitive, readable code**
- Writing `driver.bulk_write_current_limit({1: 1000})` (1000mA) is clearer than raw values

✅ **You don't want to look up conversion factors**
- No need to check motor manuals for mA/bit or rad/s per unit

✅ **You're setting common configuration parameters**
- Current limits, velocity limits, temperature limits, operating modes

✅ **You want portable code across motor models**
- High-level API handles model-specific conversion factors automatically

### Use Low-Level API (Raw Register Values) When:

⚙️ **You need direct hardware control**
- Special registers not covered by high-level API
- Custom calibration or factory configuration

⚙️ **You're optimizing performance**
- Pre-compute conversions once and write raw values multiple times

⚙️ **You're working with undocumented registers**
- Experimental features or reverse-engineered parameters

⚙️ **You need exact register values**
- Debugging hardware issues, matching vendor examples

---

## API Reference

### Dynamixel High-Level API

```python
from leropilot.services.hardware.motor_drivers.dynamixel import DynamixelDriver

driver = DynamixelDriver("/dev/ttyUSB0")
driver.connect()

# Set current limit (mA)
driver.bulk_write_current_limit({
    1: 1000,  # 1000mA = 1A
    2: 800,   # 800mA
    3: 1200,  # 1200mA
})

# Set velocity limit (rad/s)
driver.bulk_write_velocity_limit({
    1: 2.0,   # 2.0 rad/s
    2: 1.5,   # 1.5 rad/s
    3: 2.5,   # 2.5 rad/s
})

# Set temperature limit (°C)
driver.bulk_write_temperature_limit({
    1: 70,    # 70°C
    2: 70,
    3: 65,
})

# Set operating mode (0=Current, 1=Velocity, 3=Position, etc.)
driver.bulk_write_operating_mode({
    1: 3,  # Position control
    2: 3,
    3: 3,
})

# Set drive mode (0=Normal, 1=Reverse)
driver.bulk_write_drive_mode({
    1: 0,  # Normal
    2: 1,  # Reverse
    3: 0,
})
```

**Conversion Factors (DynamixelUnits):**
- Current: 2.69 mA/unit (X-series default; check manual for your model)
- Velocity: 0.02398 rad/s/unit (0.229 rpm/unit × 2π/60)
- Temperature: 1°C/unit (direct mapping)

### Feetech High-Level API

```python
from leropilot.services.hardware.motor_drivers.feetech import FeetechDriver

driver = FeetechDriver("/dev/ttyUSB0")
driver.connect()

# Set current limit (mA)
driver.bulk_write_current_limit({
    1: 500,   # 500mA
    2: 500,
    3: 400,
})

# Set velocity limit (rad/s)
driver.bulk_write_velocity_limit({
    1: 1.5,   # 1.5 rad/s
    2: 1.0,
    3: 2.0,
})

# Set temperature limit (°C)
driver.bulk_write_temperature_limit({
    1: 65,    # 65°C
    2: 65,
    3: 60,
})

# Set operating mode (0=Position, 1=Velocity, 3=Step)
driver.bulk_write_operating_mode({
    1: 0,  # Position servo mode
    2: 0,
    3: 0,
})
```

**Conversion Factors (FeetechUnits):**
- Current: ~6.5 mA/unit (STS3215; approximate, check manual)
- Velocity: 0.00153 rad/s/unit (2π/4096, for 4096 encoder resolution)
- Temperature: 1°C/unit (direct mapping)

### Damiao: Why No High-Level API?

Damiao motors use **MIT mode control** where **position, velocity, and torque are already in physical units**:

```python
from leropilot.services.hardware.motor_drivers.damiao import DamiaoCAN_Driver

driver = DamiaoCAN_Driver("can0")
driver.connect()

# Control in physical units directly (no conversion needed!)
driver.set_position(
    motor_id=(1, 257),  # (send_id, recv_id)
    pos_rad=1.57,       # 1.57 radians (π/2)
    kp=50.0,            # P gain
    kd=2.0,             # D gain
    pmax=12.5,          # Position limit: ±12.5 rad
    vmax=30.0,          # Velocity limit: 30 rad/s
    tmax=10.0,          # Torque limit: 10 N·m
)
```

**Why Damiao is Different:**
- ✅ MIT mode accepts rad, rad/s, N·m directly (no register conversion!)
- ⚠️ CAN protocol has **limited configuration write support**:
  - Most parameters (PID, limits) are read-only or require factory commands
  - MIT mode parameters (pmax, vmax, tmax) are per-command, not persistent config
  - Few writable registers (e.g., motor ID) use `bulk_write_register()` with raw values

---

## Low-Level API (All Drivers)

All drivers provide `bulk_write_register()` for raw register access:

```python
# Low-level: Write raw register values
driver.bulk_write_register(
    motor_values={1: 372, 2: 297, 3: 446},  # Raw register values
    register_addr=38,  # Current limit register (Dynamixel)
    register_len=2,    # 2 bytes (16-bit)
)

# Supports negative values (two's complement encoding)
driver.bulk_write_register(
    motor_values={1: -100, 2: 100, 3: -50},  # Signed values OK
    register_addr=104,  # Goal velocity register
    register_len=4,     # 4 bytes (32-bit)
)
```

**When Raw Values Make Sense:**
```python
# Example: You pre-computed current limits offline
CURRENT_LIMITS_RAW = {1: 372, 2: 297, 3: 446}  # Pre-converted to register values

# Batch initialization (fast, no conversion overhead)
driver.bulk_write_register(
    CURRENT_LIMITS_RAW,
    register_addr=38,
    register_len=2,
)
```

---

## Customizing Unit Conversion

If your motor model uses different conversion factors, override them:

### Dynamixel Example

```python
# Check your motor manual for the correct conversion factor
# XL330: 3.36 mA/unit (different from X-series 2.69 mA/unit)

driver.bulk_write_current_limit(
    {1: 1000, 2: 800},
    current_unit_ma=3.36,  # Override default 2.69
)
```

### Feetech Example

```python
# Custom velocity conversion for different encoder resolution
driver.bulk_write_velocity_limit(
    {1: 2.0, 2: 1.5},
    velocity_unit_rad_s=0.002,  # Custom conversion factor
)
```

---

## Implementation Details

### Conversion Formula

**High-level API internally performs:**

```python
# For current limit (mA → register value)
register_value = int(current_ma / CURRENT_MA_PER_UNIT)

# For velocity limit (rad/s → register value)
register_value = int(velocity_rad_s / VELOCITY_RAD_S_PER_UNIT)

# For temperature limit (°C → register value)
register_value = int(temperature_c / TEMPERATURE_C_PER_UNIT)
```

**Then calls low-level API:**

```python
self.bulk_write_register(
    register_values,
    register_addr=DynamixelRegisters.CURRENT_LIMIT[0],
    register_len=DynamixelRegisters.CURRENT_LIMIT[1],
)
```

### Two's Complement Encoding

Both high-level and low-level APIs support **signed integers**:

```python
# Negative values are automatically encoded using two's complement
driver.bulk_write_velocity_limit({1: -2.0, 2: 2.0})  # Reverse and forward

# Internally:
# -2.0 rad/s → -83 (raw value) → 0xFFAD (two's complement, 16-bit)
#  2.0 rad/s → +83 (raw value) → 0x0053
```

**Encoding Logic (16-bit example):**

```python
# Python's bitwise AND automatically handles two's complement
value = -100
unsigned = value & 0xFFFF  # → 0xFF9C (65436)

# For 32-bit:
unsigned = value & 0xFFFFFFFF
```

---

## Performance Comparison

### High-Level API

```python
# Conversion overhead: ~1-5μs per motor (negligible)
driver.bulk_write_current_limit({1: 1000, 2: 800, 3: 1200})
```

**Cost:** 3 divisions + 1 batch write ≈ **0.5-1ms total**

### Low-Level API

```python
# No conversion overhead
driver.bulk_write_register({1: 372, 2: 297, 3: 446}, addr=38, len=2)
```

**Cost:** 1 batch write ≈ **0.5ms total**

**Verdict:** High-level API overhead is **negligible** (<1% of total time). Batch write dominates performance.

---

## Best Practices

### ✅ DO

```python
# Use high-level API for initialization and configuration
driver.bulk_write_current_limit({1: 1000, 2: 1000, 3: 800})
driver.bulk_write_velocity_limit({1: 2.0, 2: 2.0, 3: 1.5})
driver.bulk_write_temperature_limit({1: 70, 2: 70, 3: 70})

# Use low-level API for advanced/undocumented registers
driver.bulk_write_register({1: 0x05, 2: 0x05}, addr=11, len=1)  # Operating mode
```

### ❌ DON'T

```python
# Don't manually convert units when high-level API exists
current_raw = {1: int(1000 / 2.69), 2: int(800 / 2.69)}  # BAD: manual conversion
driver.bulk_write_register(current_raw, addr=38, len=2)

# Use high-level API instead:
driver.bulk_write_current_limit({1: 1000, 2: 800})  # GOOD: automatic conversion
```

```python
# Don't use high-level API in tight control loops if pre-conversion is possible
for i in range(1000):
    driver.bulk_write_current_limit({1: 1000})  # BAD: repeated conversion overhead

# Pre-convert once:
current_raw = int(1000 / 2.69)
for i in range(1000):
    driver.bulk_write_register({1: current_raw}, addr=38, len=2)  # GOOD: no conversion
```

---

## Summary

| Feature | High-Level API | Low-Level API |
|---------|----------------|---------------|
| **Units** | Physical (mA, rad/s, °C) | Raw register values |
| **Ease of Use** | ✅ Intuitive | ⚠️ Requires manual conversion |
| **Performance** | ✅ Negligible overhead | ✅ Fastest (no conversion) |
| **Portability** | ✅ Model-independent | ⚠️ Model-specific |
| **Flexibility** | ⚠️ Common registers only | ✅ Any register |
| **Use Case** | Configuration & setup | Advanced/experimental |

**Recommendation:** Use **high-level API** for 99% of use cases. Use **low-level API** only for:
- Undocumented/experimental registers
- Performance-critical pre-converted loops
- Direct hardware debugging

---

## Related Documentation

- [Bulk Register Initialization](./bulk_register_initialization.md) - Performance optimization guide
- [Motor Driver Base API](../../src/leropilot/services/hardware/motor_drivers/base.py) - Abstract base class
- [Dynamixel Tables](../../src/leropilot/services/hardware/motor_drivers/dynamixel/tables.py) - Register definitions
- [Feetech Tables](../../src/leropilot/services/hardware/motor_drivers/feetech/tables.py) - Register definitions
- [Damiao Tables](../../src/leropilot/services/hardware/motor_drivers/damiao/tables.py) - Protocol constants
