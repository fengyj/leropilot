"""Example: Motor initialization using high-level physical unit APIs.

This example demonstrates how to use the dual-API design for motor initialization:
- High-level API: Physical units (mA, rad/s, °C) - recommended
- Low-level API: Raw register values - for advanced use cases

Key Benefits:
- No manual unit conversion needed
- More readable and maintainable code
- Consistent across different motor models
"""

from leropilot.services.hardware.motor_drivers.dynamixel import DynamixelDriver
from leropilot.services.hardware.motor_drivers.feetech import FeetechDriver


def initialize_dynamixel_arm(port: str = "/dev/ttyUSB0") -> None:
    """Initialize a 6-DOF robot arm with Dynamixel motors using physical units.

    This replaces manual unit conversion with intuitive physical values.
    """
    driver = DynamixelDriver(port)
    driver.connect()

    # Motor IDs for 6-DOF arm
    BASE_MOTORS = [1, 2]  # Shoulder (higher current/torque)
    ELBOW_MOTORS = [3, 4]  # Elbow (moderate current)
    WRIST_GRIPPER = [5, 6]  # Wrist/gripper (lower current)

    print("=== Initializing Dynamixel Arm (High-Level API) ===")

    # Step 1: Set operating mode to position control (mode 3)
    print("\n1. Setting position control mode...")
    all_motors = BASE_MOTORS + ELBOW_MOTORS + WRIST_GRIPPER
    driver.bulk_write_operating_mode({mid: 3 for mid in all_motors})

    # Step 2: Configure current limits (physical units: mA)
    print("2. Setting current limits (mA)...")
    driver.bulk_write_current_limit(
        {
            **{mid: 1500 for mid in BASE_MOTORS},  # 1500mA (1.5A) for base
            **{mid: 1000 for mid in ELBOW_MOTORS},  # 1000mA (1A) for elbow
            **{mid: 500 for mid in WRIST_GRIPPER},  # 500mA (0.5A) for wrist/gripper
        }
    )

    # Step 3: Configure velocity limits (physical units: rad/s)
    print("3. Setting velocity limits (rad/s)...")
    driver.bulk_write_velocity_limit(
        {
            **{mid: 2.0 for mid in BASE_MOTORS},  # 2.0 rad/s for base (slower)
            **{mid: 3.0 for mid in ELBOW_MOTORS},  # 3.0 rad/s for elbow
            **{mid: 4.0 for mid in WRIST_GRIPPER},  # 4.0 rad/s for wrist/gripper (faster)
        }
    )

    # Step 4: Set temperature limits (physical units: °C)
    print("4. Setting temperature limits (°C)...")
    driver.bulk_write_temperature_limit(
        {
            **{mid: 70 for mid in BASE_MOTORS},  # 70°C for base (higher load)
            **{mid: 70 for mid in ELBOW_MOTORS},  # 70°C for elbow
            **{mid: 65 for mid in WRIST_GRIPPER},  # 65°C for wrist/gripper (lower)
        }
    )

    # Step 5: Configure drive mode (0=normal, 1=reverse)
    print("5. Setting drive modes...")
    driver.bulk_write_drive_mode(
        {
            1: 0,  # Base 1: normal
            2: 1,  # Base 2: reverse (mirror joint)
            3: 0,  # Elbow 1: normal
            4: 0,  # Elbow 2: normal
            5: 0,  # Wrist: normal
            6: 0,  # Gripper: normal
        }
    )

    print("\n✅ Initialization complete! All motors configured with physical units.")
    driver.disconnect()


def initialize_feetech_gripper(port: str = "/dev/ttyUSB1") -> None:
    """Initialize a 2-finger gripper with Feetech motors using physical units."""
    driver = FeetechDriver(port)
    driver.connect()

    FINGER_MOTORS = [1, 2]  # Two-finger gripper

    print("\n=== Initializing Feetech Gripper (High-Level API) ===")

    # Configure for gentle grasping
    print("1. Setting position servo mode...")
    driver.bulk_write_operating_mode({mid: 0 for mid in FINGER_MOTORS})

    print("2. Setting current limits for gentle grasp (300mA)...")
    driver.bulk_write_current_limit({mid: 300 for mid in FINGER_MOTORS})

    print("3. Setting velocity limits (1.0 rad/s)...")
    driver.bulk_write_velocity_limit({mid: 1.0 for mid in FINGER_MOTORS})

    print("4. Setting temperature limits (60°C)...")
    driver.bulk_write_temperature_limit({mid: 60 for mid in FINGER_MOTORS})

    print("\n✅ Gripper ready for gentle object manipulation.")
    driver.disconnect()


def compare_apis() -> None:
    """Compare high-level vs low-level API for the same configuration."""
    driver = DynamixelDriver("/dev/ttyUSB0")
    driver.connect()

    print("\n=== API Comparison: High-Level vs Low-Level ===\n")

    # ========== HIGH-LEVEL API (RECOMMENDED) ==========
    print("🟢 HIGH-LEVEL API (Physical Units):")
    print("```python")
    print("# Set 1000mA current limit for motors 1, 2, 3")
    print("driver.bulk_write_current_limit({1: 1000, 2: 1000, 3: 1000})")
    print("```")
    print("✅ Intuitive: 1000 means 1000mA (1A)")
    print("✅ No manual conversion needed")
    print("✅ Works across different motor models\n")

    # Example execution (commented to avoid actual hardware writes)
    # driver.bulk_write_current_limit({1: 1000, 2: 1000, 3: 1000})

    # ========== LOW-LEVEL API (ADVANCED) ==========
    print("🔧 LOW-LEVEL API (Raw Register Values):")
    print("```python")
    print("# Manually convert 1000mA → register value")
    print("# For Dynamixel X-series: 2.69mA per unit")
    print("# 1000mA / 2.69 = 372 units")
    print("driver.bulk_write_register({1: 372, 2: 372, 3: 372}, addr=38, len=2)")
    print("```")
    print("⚠️ Requires manual conversion (error-prone)")
    print("⚠️ Magic number 372 is not self-documenting")
    print("⚠️ Model-specific (2.69mA/unit for X-series only)\n")

    # Example execution (commented)
    # driver.bulk_write_register({1: 372, 2: 372, 3: 372}, addr=38, len=2)

    print("📊 Verdict: Use high-level API unless you have a specific reason not to.\n")
    driver.disconnect()


def advanced_use_case_low_level() -> None:
    """Example where low-level API makes sense: pre-computed values in a control loop."""
    driver = DynamixelDriver("/dev/ttyUSB0")
    driver.connect()

    print("\n=== Advanced Use Case: Pre-Computed Register Values ===\n")

    # Scenario: 1000Hz control loop, current limit changes based on load detection
    # Pre-compute all possible current limits to avoid conversion overhead in the loop

    from leropilot.services.hardware.motor_drivers.dynamixel.tables import DynamixelUnits

    CURRENT_LIMITS_MA = [500, 750, 1000, 1250, 1500]  # Possible current limits
    CURRENT_LIMITS_RAW = {
        limit_ma: int(limit_ma / DynamixelUnits.CURRENT_MA_PER_UNIT) for limit_ma in CURRENT_LIMITS_MA
    }

    print("Pre-computed current limits (one-time cost):")
    for limit_ma, limit_raw in CURRENT_LIMITS_RAW.items():
        print(f"  {limit_ma}mA → {limit_raw} units")

    print("\n🔁 Control loop (1000Hz, no conversion overhead):")
    print("```python")
    print("for i in range(1000):  # 1000 iterations")
    print("    load = detect_load()  # Measure motor load")
    print("    if load > 0.8:")
    print("        # High load: increase current limit")
    print("        driver.bulk_write_register({1: CURRENT_LIMITS_RAW[1500]}, addr=38, len=2)")
    print("    elif load < 0.3:")
    print("        # Low load: decrease current limit")
    print("        driver.bulk_write_register({1: CURRENT_LIMITS_RAW[500]}, addr=38, len=2)")
    print("```")
    print("✅ No division overhead in the loop (pre-computed)")
    print("✅ Fast: ~0.5ms per write vs 0.51ms with conversion\n")

    driver.disconnect()


if __name__ == "__main__":
    # Example 1: Initialize robot arm with high-level API
    # initialize_dynamixel_arm()

    # Example 2: Initialize gripper with high-level API
    # initialize_feetech_gripper()

    # Example 3: Compare high-level vs low-level APIs
    compare_apis()

    # Example 4: Advanced use case for low-level API
    # advanced_use_case_low_level()
