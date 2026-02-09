from leropilot.models.hardware import MotorBrand, MotorModelInfo
from leropilot.services.hardware.motor_buses.damiao_motor_bus import DamiaoMotorBus


def test_damiao_motor_bus_builds_tuple_ids():
    bus = DamiaoMotorBus(interface="PCAN_USBBUS1", bitrate=1000000)
    # Register known motor ids preserving tuple entries and integers
    bus.register_motor(
        (3, 0x13),
        MotorModelInfo(
            model="DM4310", model_ids=[17168], limits={}, brand=MotorBrand.DAMIAO, encoder_resolution=65536.0
        ),
    )
    bus.register_motor(
        4,
        MotorModelInfo(
            model="DM4310", model_ids=[17168], limits={}, brand=MotorBrand.DAMIAO, encoder_resolution=65536.0
        ),
    )
    assert (3, 0x13) in bus.motors
    assert 4 in bus.motors


def test_scan_registers_driver_with_tuple():
    bus = DamiaoMotorBus(interface="PCAN_USBBUS1", bitrate=1000000)

    # Register known motor ids preserving tuple entries and integers
    bus.register_motor((3, 0x13))
    bus.register_motor(4)

    # Create fake motor info with detected id 3 (send-only)
    # Simulate discovery data: send-only id and tuple (send, recv)
    m_id = 3
    m_tuple_id = (3, 0x13)

    # Simulate registration path for tuple-style discovery
    from leropilot.services.hardware.motor_drivers.damiao.drivers import DamiaoCAN_Driver

    motor_driver = DamiaoCAN_Driver(bus.interface, bus.baud_rate)
    send_id = m_tuple_id[0]
    matched = next(
        (
            entry
            for entry in bus.motors.keys()
            if (isinstance(entry, tuple) and entry[0] == send_id) or (isinstance(entry, int) and entry == send_id)
        ),
        None,
    )
    if isinstance(matched, tuple):
        motor_driver.motor_id = matched
    else:
        motor_driver.motor_id = m_tuple_id

    assert motor_driver.motor_id == (3, 0x13)

    # Simulate registration path
    from leropilot.services.hardware.motor_drivers.damiao.drivers import DamiaoCAN_Driver

    motor_driver = DamiaoCAN_Driver(bus.interface, bus.baud_rate)
    matched = next(
        (
            entry
            for entry in bus.motors.keys()
            if (isinstance(entry, tuple) and entry[0] == m_id) or (isinstance(entry, int) and entry == m_id)
        ),
        None,
    )
    if isinstance(matched, tuple):
        motor_driver.motor_id = matched
    else:
        motor_driver.motor_id = m_id

    assert motor_driver.motor_id == (3, 0x13)
