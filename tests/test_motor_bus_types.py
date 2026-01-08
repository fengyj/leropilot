from leropilot.services.hardware.motor_buses.motor_bus import MotorBus
from leropilot.services.hardware.motor_buses.feetech_motor_bus import FeetechMotorBus
from leropilot.services.hardware.motor_buses.dynamixel_motor_bus import DynamixelMotorBus
from leropilot.services.hardware.motor_buses.damiao_motor_bus import DamiaoMotorBus


def test_motorbus_type_lists():
    serial = set(MotorBus.serial_types())
    can = set(MotorBus.can_types())

    # Basic expectations (class objects)
    assert FeetechMotorBus in serial
    assert DynamixelMotorBus in serial
    assert DamiaoMotorBus in can

    # Ensure there's no overlap between serial and CAN sets
    assert serial.isdisjoint(can)


def test_supported_baudrates_lookup():
    # Each subclass exposes a class-level supported_baudrates
    assert FeetechMotorBus.supported_baudrates()
    assert DynamixelMotorBus.supported_baudrates()
    assert DamiaoMotorBus.supported_baudrates()

    # The base helper accepts class or string
    assert MotorBus.supported_baudrates_for(FeetechMotorBus) == FeetechMotorBus.supported_baudrates()
    assert MotorBus.supported_baudrates_for("feetech") == FeetechMotorBus.supported_baudrates()
    assert MotorBus.supported_baudrates_for("damiao") == DamiaoMotorBus.supported_baudrates()


def test_resolve_bus_class():
    # Accepts class objects
    assert MotorBus.resolve_bus_class(FeetechMotorBus) is FeetechMotorBus
    # Accepts canonical string names
    assert MotorBus.resolve_bus_class("feetech") is FeetechMotorBus
    assert MotorBus.resolve_bus_class("dynamixel") is DynamixelMotorBus
    assert MotorBus.resolve_bus_class("damiao") is DamiaoMotorBus
    # Accepts alias like 'can'
    assert MotorBus.resolve_bus_class("can") is DamiaoMotorBus
