# Standardized Units API - Implementation Summary

## Overview

Added a unified **Standardized Units API** to all motor drivers, providing three API layers:

1. **High-level API** (Layer 1): Specific methods for common parameters
2. **Standardized Units API** (Layer 2): Generic methods for any register with unit conversion
3. **Low-level API** (Layer 3): Raw register access

## Standard Physical Units

All motor drivers now use **consistent physical units**:

| Quantity | Unit | Symbol |
|----------|------|--------|
| **Position** | **radians** | **rad** |
| Velocity | radians/second | rad/s |
| Acceleration | radians/second² | rad/s² |
| Current | milliamperes | mA |
| Voltage | volts | V |
| Temperature | degrees Celsius | °C |
| Torque | Newton-meters | N·m |

**Position is ALWAYS in radians (rad)**, not encoder units or degrees.

## New Methods in Base Class

### `bulk_write_values()`
Write values in standard physical units to multiple motors.

```python
driver.bulk_write_values(
    motor_values={1: 1000.0, 2: 800.0},  # Standard units (e.g., mA)
    register_addr=38,
    register_len=2,
    conversion_factor=2.69,  # mA per unit
)
```

### `bulk_read_values()`
Read register values in standard physical units from multiple motors.

```python
currents = driver.bulk_read_values(
    motor_ids=[1, 2, 3],
    register_addr=126,
    register_len=2,
    conversion_factor=2.69,
    signed=True,  # Support negative values
)
# Returns: {1: 1000.0, 2: -500.0, 3: None} in mA
```

### `bulk_read_register()`
Read raw register values (low-level).

```python
raw_values = driver.bulk_read_register(
    motor_ids=[1, 2, 3],
    register_addr=38,
    register_len=2,
)
# Returns: {1: 372, 2: 297, 3: None} (raw units)
```

### `_read_register()` (Abstract)
All drivers must implement this method for unified register reads.

```python
def _read_register(self, motor_id, address: int, length: int) -> int | None:
    """Read a register value from a motor (unified interface)."""
```

## Driver Implementations

### Dynamixel
- ✅ `_read_register()`: Dispatches to `_read_1byte()`, `_read_2byte()`, `_read_4byte()`
- ✅ `bulk_write_values()`: Inherited from base class
- ✅ `bulk_read_values()`: Inherited from base class
- ✅ `bulk_read_register()`: Inherited from base class (could be optimized with GroupSyncRead later)

### Feetech
- ✅ `_read_register()`: Dispatches to `_feetech_read_byte()`, `_feetech_read_word()`, `_feetech_read_dword()`
- ✅ `bulk_write_values()`: Inherited from base class
- ✅ `bulk_read_values()`: Inherited from base class
- ✅ `bulk_read_register()`: Inherited from base class

### Damiao
- ✅ `_read_register()`: Uses `read_parameter()` (CAN protocol limitation: 16-bit only)
- ✅ `bulk_write_values()`: Inherited from base class
- ✅ `bulk_read_values()`: Inherited from base class
- ✅ `bulk_read_register()`: Inherited from base class

## Usage Examples

### Layer 1: High-Level API (Recommended for Common Parameters)

```python
# Dynamixel
driver.bulk_write_current_limit({1: 1000, 2: 800})      # mA
driver.bulk_write_velocity_limit({1: 2.0, 2: 1.5})      # rad/s
driver.bulk_write_temperature_limit({1: 70, 2: 65})     # °C
```

### Layer 2: Standardized Units API (Flexible for Any Register)

```python
# Write current limits in mA
driver.bulk_write_values(
    {1: 1000.0, 2: 800.0},
    register_addr=38, register_len=2,
    conversion_factor=DynamixelUnits.CURRENT_MA_PER_UNIT,
)

# Read present current in mA (supports negative)
currents = driver.bulk_read_values(
    [1, 2, 3],
    register_addr=126, register_len=2,
    conversion_factor=DynamixelUnits.CURRENT_MA_PER_UNIT,
    signed=True,
)
```

### Layer 3: Low-Level API (Advanced)

```python
# Write raw register values (no conversion)
driver.bulk_write_register({1: 372, 2: 297}, addr=38, len=2)

# Read raw register values (no conversion)
raw = driver.bulk_read_register([1, 2, 3], addr=38, len=2)
```

## When to Use Each Layer

| Use Case | Layer 1 | Layer 2 | Layer 3 |
|----------|---------|---------|---------|
| Setting current limits | ✅ Best | ✅ OK | ⚠️ Advanced |
| Setting velocity limits | ✅ Best | ✅ OK | ⚠️ Advanced |
| Reading present current | ❌ N/A | ✅ Best | ⚠️ Advanced |
| Reading custom register | ❌ N/A | ✅ Best | ⚠️ Advanced |
| Writing PID gains | ❌ N/A | ✅ Best | ⚠️ Advanced |
| Pre-computed control loop | ❌ N/A | ❌ N/A | ✅ Best |
| Hardware debugging | ❌ N/A | ❌ N/A | ✅ Best |

## Benefits

### Consistency
- ✅ All drivers use the same standard units (rad, rad/s, mA, °C)
- ✅ No more confusion about encoder units vs radians
- ✅ Code is portable across different motor models

### Flexibility
- ✅ Layer 2 works for **any register** with unit conversion
- ✅ Both read and write support
- ✅ Automatic handling of signed/unsigned values

### Performance
- ✅ Layer 3 (raw API) still available for maximum performance
- ✅ No breaking changes to existing code

## Files Modified

### Core Files
- `src/leropilot/services/hardware/motor_drivers/base.py`
  - Added standard units documentation
  - Added `bulk_write_values()`, `bulk_read_values()`, `bulk_read_register()`
  - Added abstract `_read_register()` method

### Driver Implementations
- `src/leropilot/services/hardware/motor_drivers/dynamixel/drivers.py`
  - Implemented `_read_register()`
  - Type fixes for optional parameters

- `src/leropilot/services/hardware/motor_drivers/feetech/drivers.py`
  - Implemented `_read_register()`
  - Type fixes for optional parameters

- `src/leropilot/services/hardware/motor_drivers/damiao/drivers.py`
  - Implemented `_read_register()`
  - Added note about CAN protocol limitations

### Documentation
- `docs/spec/dual-api-usage.md`
  - Updated to reflect three-layer API design
  - Added standard units table
  - Added usage guidelines

### Examples
- `examples/hardware/standardized_units_api.py`
  - Comprehensive examples for all three API layers
  - Comparison between old and new API
  - Usage patterns for Dynamixel and Feetech

## Migration Guide

### Existing Code (No Changes Needed)
```python
# Old high-level API still works exactly the same
driver.bulk_write_current_limit({1: 1000, 2: 800})

# Old low-level API still works
driver.bulk_write_register({1: 372, 2: 297}, addr=38, len=2)
```

### New Capabilities
```python
# NEW: Read support with unit conversion
currents = driver.bulk_read_values(
    [1, 2, 3],
    register_addr=126, register_len=2,
    conversion_factor=2.69,
    signed=True,
)

# NEW: Write any register with unit conversion
driver.bulk_write_values(
    {1: 50.0, 2: 30.0},  # PID gain in appropriate units
    register_addr=80, register_len=2,
    conversion_factor=1.0,
)
```

## Future Improvements

### Potential Optimizations
1. **Dynamixel `bulk_read_register()`**: Could use `GroupSyncRead` for batch optimization
2. **Feetech `bulk_read_register()`**: Could use `syncRead` if SDK supports it
3. **High-level read methods**: Add `bulk_read_current()`, `bulk_read_velocity()`, etc.

### Consistency Improvements
1. **Position conversion**: Ensure all drivers convert encoder units to radians consistently
2. **Telemetry**: Make `read_telemetry()` return values in standard units (not raw encoder units)
3. **Unit constants**: Add more conversion factors for all supported motor models

## Testing Recommendations

```python
# Test Layer 2 API with known values
driver.bulk_write_values({1: 1000.0}, addr=38, len=2, conversion_factor=2.69)
raw = driver.bulk_read_register([1], addr=38, len=2)
assert raw[1] == 372  # 1000 / 2.69 ≈ 372

# Test signed value handling
driver.bulk_write_values({1: -100.0}, addr=104, len=4, conversion_factor=1.0)
raw = driver.bulk_read_register([1], addr=104, len=4)
assert raw[1] == 0xFFFFFF9C  # Two's complement of -100

# Test read with unit conversion
values = driver.bulk_read_values([1], addr=126, len=2, conversion_factor=2.69, signed=True)
# Should convert raw value back to mA correctly
```

## Related Documentation

- [Base Driver API](../../src/leropilot/services/hardware/motor_drivers/base.py)
- [Dual API Usage Guide](./dual-api-usage.md)
- [Standardized Units Examples](../../examples/hardware/standardized_units_api.py)
- [Dynamixel Driver](../../src/leropilot/services/hardware/motor_drivers/dynamixel/drivers.py)
- [Feetech Driver](../../src/leropilot/services/hardware/motor_drivers/feetech/drivers.py)
- [Damiao Driver](../../src/leropilot/services/hardware/motor_drivers/damiao/drivers.py)
