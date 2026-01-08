# ruff: noqa
from leropilot.services.hardware.motor_drivers.base import MotorUtil
from leropilot.models.hardware import MotorBrand


def test_find_dynamixel_ax12a():
    m = MotorUtil.find_motor(MotorBrand.DYNAMIXEL, "AX-12A")
    assert m is not None
    assert m.model == "AX-12A"


def test_find_feetech_variant():
    m = MotorUtil.find_motor("feetech", "STS3215", "STS3215-C001")
    assert m is not None
    assert m.variant == "STS3215-C001"


def test_find_feetech_base_fallback():
    # Requesting a non-existent variant should fall back to base model
    m = MotorUtil.find_motor("feetech", "STS3215", "NONEXISTENT")
    assert m is not None
    assert m.variant is None


def test_case_insensitive_lookup():
    m = MotorUtil.find_motor("DYNAMIXEL", "ax-12a")
    assert m is not None
    assert m.model == "AX-12A"