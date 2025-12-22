#!/usr/bin/env python
"""
Example: URDF Validator

Validate URDF robot description files for LeRobot integration.

Usage:
    python -m examples.hardware.urdf_validator <urdf_file>

Example:
    python -m examples.hardware.urdf_validator ./leropilot_v1.urdf
"""

import logging
import sys
import json
from pathlib import Path
from leropilot.services.hardware.urdf_validator import URDFValidator

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def main():
    """Validate a URDF file"""
    if len(sys.argv) < 2:
        print("Usage: python urdf_validator.py <urdf_file>")
        print("\nExample:")
        print("  python urdf_validator.py ./leropilot_v1.urdf")
        sys.exit(1)

    urdf_file = Path(sys.argv[1])

    if not urdf_file.exists():
        print(f"❌ File not found: {urdf_file}")
        sys.exit(1)

    print("\n" + "=" * 80)
    print(f"URDF VALIDATOR")
    print(f"File: {urdf_file}")
    print("=" * 80)

    try:
        validator = URDFValidator()

        # Validate
        print("\nValidating URDF structure...")
        result = validator.validate_file(str(urdf_file))

        # Display validation results
        print(f"\nValidation Status: {'✅ VALID' if result.get('valid') else '❌ INVALID'}")

        # Errors
        errors = result.get("errors", [])
        if errors:
            print(f"\n❌ Errors ({len(errors)}):")
            for error in errors:
                print(f"  - {error}")

        # Warnings
        warnings = result.get("warnings", [])
        if warnings:
            print(f"\n⚠️  Warnings ({len(warnings)}):")
            for warning in warnings:
                print(f"  - {warning}")

        # Joints
        joint_info = result.get("joint_info", [])
        if joint_info:
            print(f"\n🔗 Joints ({len(joint_info)}):")
            for joint in joint_info:
                jtype = joint.joint_type.upper() if hasattr(joint, 'joint_type') else "unknown"
                limits = joint.limits if hasattr(joint, 'limits') else {}
                print(f"  - {joint.name} ({jtype})")
                if limits:
                    print(f"    Limits: {limits}")

        # Links
        link_info = result.get("link_info", [])
        if link_info:
            print(f"\n🔗 Links ({len(link_info)}):")
            for link in link_info:
                print(f"  - {link.name}")

        # Motor validation (if motor spec provided)
        print("\n" + "-" * 80)
        print("Motor Count Validation:")

        # Example: validate that we have exactly 9 motors for OpenArm
        motor_counts = {
            9: "OpenArm (9 actuated joints)",
            6: "Hexapod (6 DOF)",
            4: "Quadruped (4 DOF)",
            3: "Tripod (3 DOF)",
            1: "Single arm (1 DOF)",
        }

        motor_result = validator.validate_motor_count(str(urdf_file), 9)
        is_valid, message = motor_result
        if is_valid:
            print(f"✅ Motor count valid: {message}")
        else:
            print(f"⚠️  Motor count mismatch:")
            print(f"   {message}")

        print("\n" + "=" * 80)
        print("URDF Validation Features:")
        print("  ✓ Structure validation (root link, joints, links)")
        print("  ✓ Kinematic chain checking (cycles, missing parents)")
        print("  ✓ Joint limit validation")
        print("  ✓ Motor count validation")
        print("  ✓ Link inertia checking")
        print("=" * 80 + "\n")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        logger.exception("Exception during URDF validation")


if __name__ == "__main__":
    main()
