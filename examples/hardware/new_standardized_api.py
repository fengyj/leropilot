"""Updated examples showing the new MotorModelInfo-based standardized units API.

This demonstrates how the conversion factors are now stored in MotorModelInfo,
simplifying the API and ensuring model-specific conversions.
"""

from leropilot.services.hardware.motor_drivers.dynamixel import DynamixelDriver
from leropilot.services.hardware.motor_drivers.dynamixel.tables import DynamixelRegisters


def example_new_api_with_model_info():
    """Example: Using the new API with MotorModelInfo."""
    driver = DynamixelDriver("/dev/ttyUSB0")
    driver.connect()

    # Step 1: Scan motors to get MotorModelInfo
    discovered_motors = driver.scan_motors([1, 2, 3])
    # Returns: {1: MotorModelInfo(...), 2: MotorModelInfo(...), 3: MotorModelInfo(...)}

    print("=== New API: Automatic Unit Conversion via MotorModelInfo ===\n")

    # ========== WRITE: Standard Units → Register ==========
    print("1. Writing current limits (mA) - automatic conversion:")

    motor_currents = {1: 1000.0, 2: 800.0, 3: 1200.0}  # mA

    driver.bulk_write_values(
        motor_values=motor_currents,
        motor_models=discovered_motors,  # MotorModelInfo for each motor
        register_addr=DynamixelRegisters.CURRENT_LIMIT[0],
        register_len=DynamixelRegisters.CURRENT_LIMIT[1],
        unit_type="current",  # Driver automatically uses model.current_unit_ma_per_bit
    )
    print(f"   ✓ Wrote {motor_currents} (mA)")
    print("   → Conversion factors automatically from MotorModelInfo\n")

    # ========== READ: Register → Standard Units ==========
    print("2. Reading present current (mA) - automatic conversion:")

    currents_ma = driver.bulk_read_values(
        motor_models=discovered_motors,
        register_addr=DynamixelRegisters.PRESENT_CURRENT[0],
        register_len=DynamixelRegisters.PRESENT_CURRENT[1],
        unit_type="current",
        signed=True,  # Present current can be negative
    )
    print(f"   Present currents: {currents_ma} (mA)")
    print("   → Each motor uses its own model-specific conversion factor\n")

    # ========== Different Motor Models ==========
    print("3. Handling different motor models automatically:")
    print("   Motor 1: XM430 (2.69 mA/bit)")
    print("   Motor 2: XL330 (3.36 mA/bit)")
    print("   Motor 3: XM430 (2.69 mA/bit)")
    print("   → Same API call, different conversions per model!\n")

    # ========== Velocity Example ==========
    print("4. Writing velocity limits (rad/s):")

    motor_velocities = {1: 2.0, 2: 1.5, 3: 2.5}  # rad/s

    driver.bulk_write_values(
        motor_values=motor_velocities,
        motor_models=discovered_motors,
        register_addr=DynamixelRegisters.VELOCITY_LIMIT[0],
        register_len=DynamixelRegisters.VELOCITY_LIMIT[1],
        unit_type="velocity",  # Uses model.velocity_ratio
    )
    print(f"   ✓ Wrote {motor_velocities} (rad/s)\n")

    driver.disconnect()
    print("✅ All operations completed with automatic model-specific conversions!")


def example_benefits_vs_old_api():
    """Compare old API vs new API."""

    print("\n=== API Comparison: Old vs New ===\n")

    print("❌ OLD API (Manual conversion factor):")
    print("```python")
    print("# Problem 1: Need to know conversion factor")
    print("driver.bulk_write_values(")
    print("    {1: 1000.0, 2: 800.0},")
    print("    register_addr=38,")
    print("    register_len=2,")
    print("    conversion_factor=2.69,  # Hard-coded! What if different models?")
    print(")")
    print("")
    print("# Problem 2: Mixed motor models need separate calls")
    print("driver.bulk_write_values(")
    print("    {1: 1000.0},  # XM430: 2.69 mA/bit")
    print("    ..., conversion_factor=2.69")
    print(")")
    print("driver.bulk_write_values(")
    print("    {2: 800.0},  # XL330: 3.36 mA/bit")
    print("    ..., conversion_factor=3.36")
    print(")")
    print("```\n")

    print("✅ NEW API (Automatic from MotorModelInfo):")
    print("```python")
    print("# Solution: Motor models contain conversion factors")
    print("motor_models = driver.scan_motors([1, 2, 3])")
    print("# {1: MotorModelInfo(model='XM430', current_unit_ma_per_bit=2.69, ...),")
    print("#  2: MotorModelInfo(model='XL330', current_unit_ma_per_bit=3.36, ...),")
    print("#  3: MotorModelInfo(model='XM430', current_unit_ma_per_bit=2.69, ...)}")
    print("")
    print("# Single call handles all motors with correct conversions")
    print("driver.bulk_write_values(")
    print("    motor_values={1: 1000.0, 2: 800.0, 3: 1200.0},")
    print("    motor_models=motor_models,  # Conversion factors from here")
    print("    register_addr=38,")
    print("    register_len=2,")
    print("    unit_type='current',  # Driver picks the right factor")
    print(")")
    print("# → Motor 1: 1000/2.69 = 372 units")
    print("# → Motor 2: 800/3.36 = 238 units")
    print("# → Motor 3: 1200/2.69 = 446 units")
    print("```\n")

    print("📊 Benefits:")
    print("   ✅ No manual conversion factor lookup")
    print("   ✅ Handles mixed motor models automatically")
    print("   ✅ Model-specific conversions guaranteed correct")
    print("   ✅ Simpler API (one less parameter)")
    print("   ✅ Less error-prone (no hard-coded magic numbers)\n")


def example_read_telemetry_units():
    """Check what units read_telemetry returns."""
    driver = DynamixelDriver("/dev/ttyUSB0")
    driver.connect()

    print("\n=== read_telemetry() Return Units ===\n")

    motor_models = driver.scan_motors([1])
    telemetry = driver.read_telemetry(1, motor_models[1])

    print(f"Position: {telemetry.position}")
    print("   ⚠️  Currently RAW encoder units (NOT radians yet)")
    print("   → TODO: Should convert to radians using model.position_to_radian_ratio\n")

    print(f"Velocity: {telemetry.velocity}")
    print("   ✅ Should be in rad/s (using model.velocity_ratio)")
    print("   → Check if already converted\n")

    print(f"Current: {telemetry.current}")
    print("   ✅ Should be in mA (using model.current_unit_ma_per_bit)")
    print("   → Check if already converted\n")

    print(f"Temperature: {telemetry.temperature}")
    print("   ✅ Should be in °C (using model.temperature_unit_c_per_bit)")
    print("   → Usually 1:1 mapping\n")

    print(f"Voltage: {telemetry.voltage}")
    print("   ✅ Should be in V (using model.voltage_unit_v_per_bit)")
    print("   → Check if already converted\n")

    driver.disconnect()


if __name__ == "__main__":
    # Example 1: New API with MotorModelInfo
    # example_new_api_with_model_info()

    # Example 2: Benefits comparison
    example_benefits_vs_old_api()

    # Example 3: Check telemetry units
    # example_read_telemetry_units()
