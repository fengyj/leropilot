"""Test conversion factors in MotorModelInfo.

This example verifies that conversion factors have been properly populated
in all MotorModelInfo instances and demonstrates how to use the new
bulk_write_values / bulk_read_values API.
"""

from leropilot.services.hardware.motor_drivers.damiao.tables import DAMAIO_MODELS_LIST
from leropilot.services.hardware.motor_drivers.dynamixel.tables import DYNAMIXEL_MODELS_LIST
from leropilot.services.hardware.motor_drivers.feetech.tables import FEETECH_MODELS_LIST


def check_conversion_factors():
    """Check that all MotorModelInfo instances have conversion factors."""

    print("=" * 80)
    print("Checking Dynamixel models for conversion factors...")
    print("=" * 80)

    for model in DYNAMIXEL_MODELS_LIST:
        print(f"\n{model.model} ({model.variant or 'base'})")
        print(f"  current_unit_ma_per_bit:        {model.current_unit_ma_per_bit}")
        print(f"  voltage_unit_v_per_bit:         {model.voltage_unit_v_per_bit}")
        print(f"  temperature_unit_c_per_bit:     {model.temperature_unit_c_per_bit}")
        print(f"  acceleration_unit_rad_s2_per_bit: {model.acceleration_unit_rad_s2_per_bit}")

        # Check for missing values
        if model.current_unit_ma_per_bit is None:
            print("  ⚠️  WARNING: current_unit_ma_per_bit is None")
        if model.voltage_unit_v_per_bit is None:
            print("  ⚠️  WARNING: voltage_unit_v_per_bit is None")
        if model.temperature_unit_c_per_bit is None:
            print("  ⚠️  WARNING: temperature_unit_c_per_bit is None")

    print("\n" + "=" * 80)
    print("Checking Feetech models for conversion factors...")
    print("=" * 80)

    for model in FEETECH_MODELS_LIST:
        print(f"\n{model.model} ({model.variant or 'base'})")
        print(f"  current_unit_ma_per_bit:        {model.current_unit_ma_per_bit}")
        print(f"  voltage_unit_v_per_bit:         {model.voltage_unit_v_per_bit}")
        print(f"  temperature_unit_c_per_bit:     {model.temperature_unit_c_per_bit}")
        print(f"  acceleration_unit_rad_s2_per_bit: {model.acceleration_unit_rad_s2_per_bit}")

        # Check for missing values
        if model.current_unit_ma_per_bit is None:
            print("  ⚠️  WARNING: current_unit_ma_per_bit is None")
        if model.voltage_unit_v_per_bit is None:
            print("  ⚠️  WARNING: voltage_unit_v_per_bit is None")
        if model.temperature_unit_c_per_bit is None:
            print("  ⚠️  WARNING: temperature_unit_c_per_bit is None")

    print("\n" + "=" * 80)
    print("Checking Damiao models for conversion factors...")
    print("=" * 80)

    for model in DAMAIO_MODELS_LIST:
        print(f"\n{model.model} ({model.variant or 'base'})")
        print(f"  current_unit_ma_per_bit:        {model.current_unit_ma_per_bit}")
        print(f"  voltage_unit_v_per_bit:         {model.voltage_unit_v_per_bit}")
        print(f"  temperature_unit_c_per_bit:     {model.temperature_unit_c_per_bit}")
        print(f"  acceleration_unit_rad_s2_per_bit: {model.acceleration_unit_rad_s2_per_bit}")

        # Check for missing values
        if model.current_unit_ma_per_bit is None:
            print("  ⚠️  WARNING: current_unit_ma_per_bit is None")
        if model.voltage_unit_v_per_bit is None:
            print("  ⚠️  WARNING: voltage_unit_v_per_bit is None")
        if model.temperature_unit_c_per_bit is None:
            print("  ⚠️  WARNING: temperature_unit_c_per_bit is None")

    print("\n" + "=" * 80)
    print("✅ All models checked!")
    print("=" * 80)


def demonstrate_api_usage():
    """Demonstrate how to use the new bulk_write_values API."""

    print("\n" + "=" * 80)
    print("Example: Using bulk_write_values with mixed motor models")
    print("=" * 80)

    # Simulate having two different Dynamixel motors
    from leropilot.services.hardware.motor_drivers.dynamixel.tables import select_model_for_number

    xm430_model = select_model_for_number(1020)  # XM430-W350
    xl330_model = select_model_for_number(1190)  # XL330-M077

    print(f"\nMotor 1: {xm430_model.model} - current factor: {xm430_model.current_unit_ma_per_bit} mA/unit")
    print(f"Motor 2: {xl330_model.model} - current factor: {xl330_model.current_unit_ma_per_bit} mA/unit")

    # Motor IDs and their models
    motor_models = {
        1: xm430_model,
        2: xl330_model,
    }

    # Current values in standard units (mA)
    current_values = {
        1: 1000.0,  # 1000mA for motor 1
        2: 800.0,  # 800mA for motor 2
    }

    print("\n--- Writing current limits in standard units (mA) ---")
    print(f"Motor 1: {current_values[1]} mA → {int(current_values[1] / xm430_model.current_unit_ma_per_bit)} units")
    print(f"Motor 2: {current_values[2]} mA → {int(current_values[2] / xl330_model.current_unit_ma_per_bit)} units")

    print("\nWith the new API, you would call:")
    print("  driver.bulk_write_values(")
    print(f"      motor_values={current_values},")
    print(f"      motor_models={motor_models},")
    print("      register_addr=38,  # Current Limit register")
    print("      register_len=2,")
    print("      unit_type='current',")
    print("  )")
    print("\nThe driver automatically:")
    print("  1. Looks up the conversion factor for each motor")
    print("  2. Converts mA to register units per motor")
    print("  3. Writes all values in a single bulk transaction")


if __name__ == "__main__":
    check_conversion_factors()
    demonstrate_api_usage()
