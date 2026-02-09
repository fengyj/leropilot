# Standardized Units API - Design Update

## Summary

Updated the standardized units API to use `MotorModelInfo` for automatic conversion factor lookup, eliminating the need for manual conversion factor parameters.

## Key Changes

### 1. MotorModelInfo Extension

Added conversion factor fields to `MotorModelInfo`:

```python
class MotorModelInfo(BaseModel):
    # Existing fields...
    position_to_radian_ratio: float | None
    velocity_ratio: float | None
    
    # NEW: Additional conversion factors
    current_unit_ma_per_bit: float | None  # mA per register unit
    voltage_unit_v_per_bit: float | None  # V per register unit
    temperature_unit_c_per_bit: float | None  # °C per register unit
    acceleration_unit_rad_s2_per_bit: float | None  # rad/s² per register unit
```

### 2. Simplified API Signature

**Old API** (manual conversion factor):
```python
driver.bulk_write_values(
    motor_values={1: 1000.0, 2: 800.0},
    register_addr=38,
    register_len=2,
    conversion_factor=2.69,  # ❌ Manual lookup required
)

driver.bulk_read_values(
    motor_ids=[1, 2, 3],  # ❌ No model info
    register_addr=126,
    register_len=2,
    conversion_factor=2.69,  # ❌ Assumes all motors use same factor
    signed=True,
)
```

**New API** (automatic from MotorModelInfo):
```python
motor_models = driver.scan_motors([1, 2, 3])
# {1: MotorModelInfo(...), 2: MotorModelInfo(...), ...}

driver.bulk_write_values(
    motor_values={1: 1000.0, 2: 800.0},
    motor_models=motor_models,  # ✅ Contains conversion factors
    register_addr=38,
    register_len=2,
    unit_type="current",  # ✅ Driver picks the right factor
)

driver.bulk_read_values(
    motor_models=motor_models,  # ✅ Model-specific conversions
    register_addr=126,
    register_len=2,
    unit_type="current",
    signed=True,
)
```

### 3. Benefits

| Benefit | Old API | New API |
|---------|---------|---------|
| **Manual conversion lookup** | ❌ Required | ✅ Automatic |
| **Mixed motor models** | ❌ Separate calls | ✅ Single call |
| **Error-prone** | ❌ Magic numbers | ✅ Type-safe enum |
| **Model-specific accuracy** | ⚠️ Manual | ✅ Guaranteed |
| **API simplicity** | ⚠️ Complex | ✅ Simple |

### 4. Migration Example

#### Before:
```python
# Step 1: Look up conversion factor manually
# Dynamixel X-series: 2.69 mA/unit
# Dynamixel XL330: 3.36 mA/unit

# Step 2: Write (all motors must use same factor)
driver.bulk_write_values(
    {1: 1000.0, 2: 800.0},
    register_addr=38, register_len=2,
    conversion_factor=2.69,  # Assumes all are X-series
)

# Step 3: If mixed models, need separate calls
driver.bulk_write_values(
    {3: 1200.0},  # XL330
    register_addr=38, register_len=2,
    conversion_factor=3.36,  # Different factor
)
```

#### After:
```python
# Step 1: Get motor models (conversion factors included)
motor_models = driver.scan_motors([1, 2, 3])

# Step 2: Write all motors (automatic per-model conversion)
driver.bulk_write_values(
    motor_values={1: 1000.0, 2: 800.0, 3: 1200.0},
    motor_models=motor_models,  # Motor 1,2: 2.69, Motor 3: 3.36
    register_addr=38, register_len=2,
    unit_type="current",
)
# → Motor 1: 1000/2.69 = 372 units
# → Motor 2: 800/2.69 = 297 units
# → Motor 3: 1200/3.36 = 357 units (different conversion!)
```

## Telemetry Unit Status

### Current State (as of implementation)

| Field | Current Unit | Standard Unit | Status |
|-------|-------------|---------------|--------|
| **position** | Raw encoder counts | rad | ⚠️ TODO |
| **velocity** | Raw hardware units | rad/s | ⚠️ TODO |
| **current** | mA | mA | ✅ Done |
| **voltage** | V | V | ✅ Done |
| **temperature** | °C | °C | ✅ Done |

**Note:** `read_telemetry()` and `bulk_read_telemetry()` currently return:
- ✅ **current, voltage, temperature** in standard units (mA, V, °C)
- ⚠️ **position, velocity** in RAW units (not yet converted to rad/rad/s)

### Recommendation

Update telemetry methods to return **all values in standard units**:

```python
def read_telemetry(...) -> MotorTelemetry:
    # Current: Returns raw encoder counts
    position_raw = self._read_position(motor_id, model_info)
    
    # TODO: Convert to radians
    position_rad = position_raw * model_info.position_to_radian_ratio
    
    # Similar for velocity
    velocity_raw = self._read_velocity(motor_id, model_info)
    velocity_rad_s = velocity_raw * model_info.velocity_ratio
    
    return MotorTelemetry(
        position=position_rad,  # Now in rad!
        velocity=velocity_rad_s,  # Now in rad/s!
        current=current_ma,  # Already in mA
        voltage=voltage_v,  # Already in V
        temperature=temp_c,  # Already in °C
        ...
    )
```

## Implementation Details

### Internal Helper Method

```python
def _get_conversion_factor(
    self,
    model_info: MotorModelInfo,
    unit_type: Literal["current", "velocity", "acceleration", "temperature", "voltage"],
) -> float | None:
    """Get the appropriate conversion factor from MotorModelInfo."""
    if unit_type == "current":
        return model_info.current_unit_ma_per_bit
    elif unit_type == "velocity":
        return model_info.velocity_ratio
    elif unit_type == "acceleration":
        return model_info.acceleration_unit_rad_s2_per_bit
    elif unit_type == "temperature":
        return model_info.temperature_unit_c_per_bit
    elif unit_type == "voltage":
        return model_info.voltage_unit_v_per_bit
    else:
        return None
```

### Error Handling

```python
# Raises ValueError if conversion factor not available
driver.bulk_write_values(
    motor_values={1: 1000.0},
    motor_models={1: model_info_without_current_factor},
    register_addr=38, register_len=2,
    unit_type="current",
)
# → ValueError: No current conversion factor defined for motor model XM430/W350
```

## Next Steps

### TODO: Update MotorModelInfo Instances

All motor model definitions in tables.py files need to be updated with conversion factors:

```python
# Before
MotorModelInfo(
    model="XM430",
    encoder_resolution=4096.0,
    position_to_radian_ratio=(2 * math.pi) / 4096,
    velocity_ratio=0.229 * 2 * math.pi / 60,
    # Missing: current, voltage, temperature, acceleration
)

# After
MotorModelInfo(
    model="XM430",
    encoder_resolution=4096.0,
    position_to_radian_ratio=(2 * math.pi) / 4096,
    velocity_ratio=0.229 * 2 * math.pi / 60,
    current_unit_ma_per_bit=2.69,  # NEW
    voltage_unit_v_per_bit=0.1,  # NEW
    temperature_unit_c_per_bit=1.0,  # NEW
    acceleration_unit_rad_s2_per_bit=0.3738,  # NEW
)
```

### TODO: Update Telemetry to Return Standard Units

Modify `read_telemetry()` and `bulk_read_telemetry()` to return:
- ✅ position in **rad** (not raw encoder counts)
- ✅ velocity in **rad/s** (not raw hardware units)

### TODO: Update High-Level API Methods

Update existing high-level wrappers to use the new `bulk_write_values` API:

```python
def bulk_write_current_limit(
    self,
    motor_currents: dict[int, float],
    motor_models: dict[int, MotorModelInfo],  # NEW parameter
) -> dict[int, bool]:
    """Set current limit for multiple motors."""
    return self.bulk_write_values(
        motor_values=motor_currents,
        motor_models=motor_models,
        register_addr=DynamixelRegisters.CURRENT_LIMIT[0],
        register_len=DynamixelRegisters.CURRENT_LIMIT[1],
        unit_type="current",
    )
```

## Questions & Answers

### Q: What about models with different conversion factors?

**A:** The new design handles this automatically! Each motor uses its own `MotorModelInfo`, so different models can have different conversion factors:

```python
motor_models = {
    1: MotorModelInfo(model="XM430", current_unit_ma_per_bit=2.69),
    2: MotorModelInfo(model="XL330", current_unit_ma_per_bit=3.36),
}

driver.bulk_write_values(
    {1: 1000.0, 2: 1000.0},  # Same mA value
    motor_models,
    unit_type="current",
)
# → Motor 1: 372 units (1000/2.69)
# → Motor 2: 298 units (1000/3.36)
```

### Q: What if MotorModelInfo doesn't have a conversion factor?

**A:** The method raises a `ValueError`:

```python
ValueError: No current conversion factor defined for motor model 
            DYNAMIXEL/XM430/W350
```

This ensures conversions are never silently wrong.

### Q: Is this a breaking change?

**A:** Partially:
- ✅ **Low-level API** (`bulk_write_register`, `bulk_read_register`) unchanged
- ⚠️ **Standardized units API** signature changed (added `motor_models`, `unit_type`)
- ⚠️ **High-level API** will need updates to accept `motor_models`

Recommendation: Keep both old and new signatures temporarily for migration period.

## Related Files

- [models/hardware.py](../../src/leropilot/models/hardware.py) - MotorModelInfo definition
- [base.py](../../src/leropilot/services/hardware/motor_drivers/base.py) - API implementation
- [new_standardized_api.py](../../examples/hardware/new_standardized_api.py) - Usage examples
- [standardized-units-api-summary.md](./standardized-units-api-summary.md) - Previous implementation

## Migration Checklist

- [ ] Update all MotorModelInfo instances with conversion factors
- [ ] Update telemetry methods to return position/velocity in standard units
- [ ] Update high-level API methods to accept motor_models parameter
- [ ] Add migration guide for existing code
- [ ] Update documentation and examples
- [ ] Add tests for mixed motor model scenarios
