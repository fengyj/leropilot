import pytest

from leropilot.models.hardware import MotorBrand, MotorModelInfo
from leropilot.services.hardware.motor_buses.damiao_motor_bus import DamiaoMotorBus
from leropilot.services.hardware.motor_buses.dynamixel_motor_bus import DynamixelMotorBus
from leropilot.services.hardware.motor_buses.feetech_motor_bus import FeetechMotorBus
from leropilot.services.hardware.robots import RobotManager


def test_discover_motor_buses_serial(monkeypatch: pytest.MonkeyPatch) -> None:
    # Simulate one serial port and have FeetechMotorBus report motors
    from leropilot.models.hardware import PlatformSerialPort

    def fake_serial_ports_one(_self: object) -> list[PlatformSerialPort]:
        return [
            PlatformSerialPort(
                port='/dev/ttyUSB0',
                description='FTDI USB Serial',
                serial_number='SN1',
                manufacturer='Mfg',
            )
        ]

    monkeypatch.setattr(
        'leropilot.services.hardware.platform_adapter.PlatformAdapter.discover_serial_ports',
        fake_serial_ports_one,
    )

    # Feetech scans return one motor
    monkeypatch.setattr(FeetechMotorBus, 'connect', lambda self: True)

    def fake_scan_feetech(self: object, id_range: object | None = None) -> dict:
        return {1: MotorModelInfo(model='X', model_ids=[1], limits={}, brand=MotorBrand.FEETECH)}

    monkeypatch.setattr(FeetechMotorBus, 'scan_motors', fake_scan_feetech)

    # Ensure other buses do not falsely report motors
    monkeypatch.setattr(DynamixelMotorBus, 'connect', lambda self: False)
    monkeypatch.setattr(DamiaoMotorBus, 'connect', lambda self: False)

    manager = RobotManager()
    results = manager._discovery_service.discover_motor_buses()

    # results are tuples (bus, serial_number, manufacturer). Implementations may return proxy
    # objects whose class name matches the real class to avoid keeping hardware open.
    assert any(item[0].__class__.__name__ == "FeetechMotorBus" for item in results)
    # ensure serial number propagated
    assert any(item[1] == 'SN1' for item in results)


def test_discover_motor_buses_with_filters(monkeypatch: pytest.MonkeyPatch) -> None:
    # Simulate both serial and CAN interfaces
    from leropilot.models.hardware import PlatformSerialPort

    def fake_serial_ports_two(_self: object) -> list[PlatformSerialPort]:
        return [
            PlatformSerialPort(
                port='/dev/ttyUSB0',
                description='FTDI USB Serial',
                serial_number='SN1',
                manufacturer='Mfg',
            )
        ]

    monkeypatch.setattr(
        'leropilot.services.hardware.platform_adapter.PlatformAdapter.discover_serial_ports',
        fake_serial_ports_two,
    )
    from leropilot.models.hardware import PlatformCANInterface

    monkeypatch.setattr(
        'leropilot.services.hardware.platform_adapter.PlatformAdapter.discover_can_interfaces',
        lambda self: [PlatformCANInterface(interface='can0', manufacturer='CANInc')]
    )

    # Feetech succeeds on serial @ 1000000
    monkeypatch.setattr(FeetechMotorBus, 'connect', lambda self: True)

    def fake_scan_feetech(self: object, id_range: object | None = None) -> dict:
        return {1: MotorModelInfo(model='X', model_ids=[1], limits={}, brand=MotorBrand.FEETECH)}

    monkeypatch.setattr(FeetechMotorBus, 'scan_motors', fake_scan_feetech)

    # Damiao would succeed on CAN @ 1000000 but we will not include it in filters below
    monkeypatch.setattr(DamiaoMotorBus, 'connect', lambda self: True)

    def fake_scan_damiao(self: object, id_range: object | None = None) -> dict:
        return {(1, 1): MotorModelInfo(model='D', model_ids=[2], limits={}, brand=MotorBrand.DAMIAO)}

    monkeypatch.setattr(DamiaoMotorBus, 'scan_motors', fake_scan_damiao)

    manager = RobotManager()
    # Only probe Feetech @ 1000000
    results = manager._discovery_service.discover_motor_buses(filters=[('feetech', 1000000)])

    assert any(item[0].__class__.__name__ == "FeetechMotorBus" for item in results)
    # Damiao should not be present because filters restrict to feetech
    assert not any(isinstance(item[0], DamiaoMotorBus) for item in results)
