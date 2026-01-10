from leropilot.services.hardware.robots import RobotManager
from leropilot.services.hardware.motor_buses.feetech_motor_bus import FeetechMotorBus
from leropilot.services.hardware.motor_buses.dynamixel_motor_bus import DynamixelMotorBus
from leropilot.services.hardware.motor_buses.damiao_motor_bus import DamiaoMotorBus
from leropilot.models.hardware import MotorModelInfo, MotorBrand


def test_discover_motor_buses_serial(monkeypatch):
    # Simulate one serial port and have FeetechMotorBus report motors
    from leropilot.models.hardware import PlatformSerialPort

    monkeypatch.setattr(
        'leropilot.services.hardware.platform_adapter.PlatformAdapter.discover_serial_ports',
        lambda self: [PlatformSerialPort(port='/dev/ttyUSB0', description='FTDI USB Serial', serial_number='SN1', manufacturer='Mfg')]
    )

    # Feetech scans return one motor
    monkeypatch.setattr(FeetechMotorBus, 'connect', lambda self: True)
    monkeypatch.setattr(FeetechMotorBus, 'scan_motors', lambda self, id_range=None: {1: MotorModelInfo(model='X', model_ids=[1], limits={}, brand=MotorBrand.FEETECH)})

    # Ensure other buses do not falsely report motors
    monkeypatch.setattr(DynamixelMotorBus, 'connect', lambda self: False)
    monkeypatch.setattr(DamiaoMotorBus, 'connect', lambda self: False)

    manager = RobotManager()
    results = manager._discover_motor_buses()

    # results are tuples (bus, serial_number, manufacturer). Implementations may return proxy
    # objects whose class name matches the real class to avoid keeping hardware open.
    assert any(item[0].__class__.__name__ == "FeetechMotorBus" for item in results)
    # ensure serial number propagated
    assert any(item[1] == 'SN1' for item in results)


def test_discover_motor_buses_with_filters(monkeypatch):
    # Simulate both serial and CAN interfaces
    from leropilot.models.hardware import PlatformSerialPort

    monkeypatch.setattr(
        'leropilot.services.hardware.platform_adapter.PlatformAdapter.discover_serial_ports',
        lambda self: [PlatformSerialPort(port='/dev/ttyUSB0', description='FTDI USB Serial', serial_number='SN1', manufacturer='Mfg')]
    )
    from leropilot.models.hardware import PlatformCANInterface

    monkeypatch.setattr(
        'leropilot.services.hardware.platform_adapter.PlatformAdapter.discover_can_interfaces',
        lambda self: [PlatformCANInterface(interface='can0', manufacturer='CANInc')]
    )

    # Feetech succeeds on serial @ 1000000
    monkeypatch.setattr(FeetechMotorBus, 'connect', lambda self: True)
    monkeypatch.setattr(FeetechMotorBus, 'scan_motors', lambda self, id_range=None: {1: MotorModelInfo(model='X', model_ids=[1], limits={}, brand=MotorBrand.FEETECH)})

    # Damiao would succeed on CAN @ 1000000 but we will not include it in filters below
    monkeypatch.setattr(DamiaoMotorBus, 'connect', lambda self: True)
    monkeypatch.setattr(DamiaoMotorBus, 'scan_motors', lambda self, id_range=None: {(1,1): MotorModelInfo(model='D', model_ids=[2], limits={}, brand=MotorBrand.DAMIAO)})

    manager = RobotManager()
    # Only probe Feetech @ 1000000
    results = manager._discover_motor_buses(filters=[('feetech', 1000000)])

    assert any(item[0].__class__.__name__ == "FeetechMotorBus" for item in results)
    # Damiao should not be present because filters restrict to feetech
    assert not any(isinstance(item[0], DamiaoMotorBus) for item in results)
