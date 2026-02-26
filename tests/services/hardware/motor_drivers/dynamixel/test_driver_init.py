from leropilot.services.hardware.motor_drivers.dynamixel.drivers import DynamixelDriver
from leropilot.services.hardware.motor_drivers.dynamixel.tables import DynamixelRegisters


def test_dynamixel_driver_initializes_register_map():
    # Instantiating the driver should build a register map without errors
    drv = DynamixelDriver(interface="/dev/null", baud_rate=1000000)
    # Ensure a known register address exists in the internal map
    assert DynamixelRegisters.PRESENT_POSITION[0] in drv._register_map
    addr, length = drv._register_map[DynamixelRegisters.PRESENT_POSITION[0]]
    assert length in (1, 2, 4)
