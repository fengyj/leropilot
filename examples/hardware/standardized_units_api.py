"""Example: Using standardized units API for motor configuration.

This example demonstrates the new standardized units API (bulk_write_values, bulk_read_values)
which provides a uniform interface across all motor drivers.

Key Features:
- Consistent API across Dynamixel, Feetech, and Damiao drivers
- Standard physical units (rad, rad/s, mA, °C, etc.)
- Automatic unit conversion based on motor model
- Read and write support for all register types
"""

from leropilot.services.hardware.motor_drivers.dynamixel import DynamixelDriver
from leropilot.services.hardware.motor_drivers.dynamixel.tables import (
    DynamixelRegisters,
    DynamixelUnits,
)
from leropilot.services.hardware.motor_drivers.feetech import FeetechDriver
from leropilot.services.hardware.motor_drivers.feetech.tables import (
    FeetechUnits,
    SCS_STS_Registers,
)


def example_dynamixel_standardized_api():
    """Example using standardized units API with Dynamixel motors."""
    driver = DynamixelDriver("/dev/ttyUSB0")
    driver.connect()

    motor_ids = [1, 2, 3]

    print("=== Dynamixel: Standardized Units API ===\n")

    # ========== WRITE: Standard Units → Register ==========
    print("1. Writing current limits using standard units (mA):")

    # Method 1: Use high-level wrapper (recommended for common parameters)
    driver.bulk_write_current_limit({1: 1000.0, 2: 800.0, 3: 1200.0})
    print("   ✓ Using bulk_write_current_limit: 1000mA, 800mA, 1200mA")

    # Method 2: Use generic standardized API (flexible for any register)
    driver.bulk_write_values(
        motor_values={1: 1000.0, 2: 800.0, 3: 1200.0},  # Standard unit: mA
        register_addr=DynamixelRegisters.CURRENT_LIMIT[0],
        register_len=DynamixelRegisters.CURRENT_LIMIT[1],
        conversion_factor=DynamixelUnits.CURRENT_MA_PER_UNIT,  # 2.69 mA/unit
    )
    print("   ✓ Using bulk_write_values: 1000mA → 372 units, 800mA → 297 units")

    # ========== READ: Register → Standard Units ==========
    print("\n2. Reading current limits in standard units (mA):")

    currents_ma = driver.bulk_read_values(
        motor_ids=[1, 2, 3],
        register_addr=DynamixelRegisters.CURRENT_LIMIT[0],
        register_len=DynamixelRegisters.CURRENT_LIMIT[1],
        conversion_factor=DynamixelUnits.CURRENT_MA_PER_UNIT,
        signed=False,  # Current limit is unsigned
    )
    print(f"   Current limits: {currents_ma}")  # {1: 1000.0, 2: 800.0, 3: 1200.0}

    # ========== READ: Present Current (Signed Value) ==========
    print("\n3. Reading present current (signed, can be negative):")

    present_currents = driver.bulk_read_values(
        motor_ids=[1, 2, 3],
        register_addr=DynamixelRegisters.PRESENT_CURRENT[0],
        register_len=DynamixelRegisters.PRESENT_CURRENT[1],
        conversion_factor=DynamixelUnits.CURRENT_MA_PER_UNIT,
        signed=True,  # Present current is signed (positive = CCW, negative = CW)
    )
    print(f"   Present currents: {present_currents}")  # {1: 450.0, 2: -200.0, 3: 0.0}

    # ========== WRITE: Velocity in rad/s ==========
    print("\n4. Writing velocity limits in standard units (rad/s):")

    driver.bulk_write_values(
        motor_values={1: 2.0, 2: 1.5, 3: 2.5},  # Standard unit: rad/s
        register_addr=DynamixelRegisters.VELOCITY_LIMIT[0],
        register_len=DynamixelRegisters.VELOCITY_LIMIT[1],
        conversion_factor=DynamixelUnits.VELOCITY_RAD_S_PER_UNIT,  # 0.02398 rad/s/unit
    )
    print("   ✓ Set: 2.0 rad/s, 1.5 rad/s, 2.5 rad/s")

    # ========== RAW REGISTER ACCESS (Advanced) ==========
    print("\n5. Low-level raw register access (for comparison):")

    # Read raw register values (no conversion)
    raw_currents = driver.bulk_read_register(
        motor_ids=[1, 2, 3],
        register_addr=DynamixelRegisters.CURRENT_LIMIT[0],
        register_len=DynamixelRegisters.CURRENT_LIMIT[1],
    )
    print(f"   Raw register values: {raw_currents}")  # {1: 372, 2: 297, 3: 446}

    # Write raw register values (no conversion)
    driver.bulk_write_register(
        motor_values={1: 372, 2: 297, 3: 446},  # Raw units
        register_addr=DynamixelRegisters.CURRENT_LIMIT[0],
        register_len=DynamixelRegisters.CURRENT_LIMIT[1],
    )
    print("   ✓ Wrote raw values: 372, 297, 446 (same as 1000mA, 800mA, 1200mA)")

    driver.disconnect()
    print("\n✅ All operations completed successfully!")


def example_feetech_standardized_api():
    """Example using standardized units API with Feetech motors."""
    driver = FeetechDriver("/dev/ttyUSB1")
    driver.connect()

    print("\n=== Feetech: Standardized Units API ===\n")

    # Write current limits in mA
    print("1. Setting current limits (mA):")
    driver.bulk_write_values(
        motor_values={1: 500.0, 2: 400.0},  # Standard unit: mA
        register_addr=SCS_STS_Registers.CURRENT_LIMIT[0],
        register_len=SCS_STS_Registers.CURRENT_LIMIT[1],
        conversion_factor=FeetechUnits.CURRENT_MA_PER_UNIT,  # 6.5 mA/unit
    )
    print("   ✓ Set: 500mA → 77 units, 400mA → 62 units")

    # Read velocity in rad/s
    print("\n2. Reading present velocity (rad/s):")
    velocities = driver.bulk_read_values(
        motor_ids=[1, 2],
        register_addr=SCS_STS_Registers.PRESENT_VELOCITY[0],
        register_len=SCS_STS_Registers.PRESENT_VELOCITY[1],
        conversion_factor=FeetechUnits.VELOCITY_RAD_S_PER_UNIT,  # 0.00153 rad/s/unit
        signed=True,  # Velocity can be negative (reverse direction)
    )
    print(f"   Present velocities: {velocities}")  # {1: 1.5, 2: -0.8}

    # Write temperature limit in °C
    print("\n3. Setting temperature limit (°C):")
    driver.bulk_write_values(
        motor_values={1: 65.0, 2: 65.0},  # Standard unit: °C
        register_addr=SCS_STS_Registers.TEMPERATURE_LIMIT[0],
        register_len=SCS_STS_Registers.TEMPERATURE_LIMIT[1],
        conversion_factor=FeetechUnits.TEMPERATURE_C_PER_UNIT,  # 1.0 °C/unit
    )
    print("   ✓ Set: 65°C (direct 1:1 mapping)")

    driver.disconnect()
    print("\n✅ Feetech configuration completed!")


def comparison_old_vs_new_api():
    """Compare old high-level API vs new standardized API."""
    driver = DynamixelDriver("/dev/ttyUSB0")
    driver.connect()

    print("\n=== API Comparison: Old vs New ===\n")

    # OLD API: High-level wrappers (still supported, recommended for common params)
    print("🟢 OLD API (High-level wrappers - still recommended for common params):")
    print("```python")
    print("driver.bulk_write_current_limit({1: 1000.0, 2: 800.0})")
    print("driver.bulk_write_velocity_limit({1: 2.0, 2: 1.5})")
    print("driver.bulk_write_temperature_limit({1: 70.0, 2: 70.0})")
    print("```")
    print("✅ Pros: Concise, self-documenting")
    print("⚠️ Cons: Limited to common parameters\n")

    # NEW API: Standardized units (flexible for any register)
    print("🆕 NEW API (Standardized units - flexible for any register):")
    print("```python")
    print("driver.bulk_write_values(")
    print("    {1: 1000.0, 2: 800.0},  # mA")
    print("    register_addr=38, register_len=2,")
    print("    conversion_factor=DynamixelUnits.CURRENT_MA_PER_UNIT")
    print(")")
    print("driver.bulk_read_values(")
    print("    [1, 2],")
    print("    register_addr=126, register_len=2,")
    print("    conversion_factor=DynamixelUnits.CURRENT_MA_PER_UNIT,")
    print("    signed=True")
    print(")")
    print("```")
    print("✅ Pros: Works for ANY register, read+write support")
    print("✅ Pros: Consistent API across all drivers")
    print("⚠️ Cons: More verbose\n")

    # RAW API: Direct register access (advanced)
    print("🔧 RAW API (Direct register access - advanced):")
    print("```python")
    print("# Manual conversion required!")
    print("raw_value = int(1000.0 / 2.69)  # 372")
    print("driver.bulk_write_register({1: 372, 2: 297}, addr=38, len=2)")
    print("raw_values = driver.bulk_read_register([1, 2], addr=38, len=2)")
    print("current_ma = raw_values[1] * 2.69  # Manual conversion back")
    print("```")
    print("⚠️ Cons: Manual conversion, error-prone")
    print("✅ Pros: Maximum control, no overhead\n")

    print("📊 Recommendation:")
    print("   - Use OLD API (wrappers) for common parameters (current, velocity, temp)")
    print("   - Use NEW API (bulk_write/read_values) for any other register with unit conversion")
    print("   - Use RAW API (bulk_write/read_register) only for debug or pre-computed values\n")

    driver.disconnect()


if __name__ == "__main__":
    # Example 1: Dynamixel standardized API
    # example_dynamixel_standardized_api()

    # Example 2: Feetech standardized API
    # example_feetech_standardized_api()

    # Example 3: API comparison
    comparison_old_vs_new_api()
