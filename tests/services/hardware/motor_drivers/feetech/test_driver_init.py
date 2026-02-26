from leropilot.services.hardware.motor_drivers.feetech.drivers import FeetechDriver
from leropilot.services.hardware.motor_drivers.feetech.tables import SCS_STS_Registers


def test_feetech_driver_initializes_register_map():
    drv = FeetechDriver(interface="/dev/null", baud_rate=1000000)
    assert SCS_STS_Registers.PRESENT_POSITION[0] in drv._register_map
    addr, length = drv._register_map[SCS_STS_Registers.PRESENT_POSITION[0]]
    assert length in (1, 2, 4)
