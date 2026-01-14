"""Tests for MotorBus implementation."""
from unittest.mock import Mock, patch

import pytest

from leropilot.models.hardware import MotorBrand, MotorModelInfo
from leropilot.services.hardware.motor_buses.damiao_motor_bus import DamiaoMotorBus
from leropilot.services.hardware.motor_buses.feetech_motor_bus import FeetechMotorBus
from leropilot.services.hardware.motor_buses.motor_bus import MotorBus
from leropilot.services.hardware.motor_drivers.base import BaseMotorDriver
from leropilot.services.hardware.motor_drivers.feetech.drivers import FeetechDriver


class MockDriver(BaseMotorDriver):
    """Mock driver for testing."""

    def __init__(self, interface: str, baud_rate: int = 1000000):
        super().__init__(interface, baud_rate)
        self.connected = False

    def connect(self) -> bool:
        self.connected = True
        return True

    def disconnect(self) -> None:
        self.connected = False

    def scan_motors(self, scan_range=None):
        return []

    def ping_motor(self, motor_id: int) -> bool:
        return True

    def read_telemetry(self, motor_id: int):
        return None

    def set_position(self, motor_id: int, position: int, speed=None) -> bool:
        return True

    def set_torque(self, motor_id: int, torque: float) -> bool:
        return True

    def reboot_motor(self, motor_id: int) -> bool:
        return True

    def is_connected(self) -> bool:
        return self.connected


def test_abstract_motor_bus() -> None:
    """Test that MotorBus is abstract and cannot be instantiated directly."""
    with pytest.raises(TypeError):
        MotorBus("test", 1000000)


def test_feetech_motor_bus_initialization() -> None:
    """Test FeetechMotorBus can be initialized."""
    bus = FeetechMotorBus("/dev/ttyUSB0", 1000000)

    assert bus.interface == "/dev/ttyUSB0"
    assert bus.baud_rate == 1000000
    assert bus.driver_class == FeetechDriver
    assert not bus.is_connected()


def test_damiao_motor_bus_initialization() -> None:
    """Test DamiaoMotorBus can be initialized."""
    bus = DamiaoMotorBus("can0", 1000000)

    assert bus.interface == "can0"
    assert bus.baud_rate == 1000000
    assert not bus.is_connected()


def test_feetech_motor_bus_connect_disconnect() -> None:
    """Test FeetechMotorBus connect/disconnect lifecycle."""
    bus = FeetechMotorBus("/dev/ttyUSB0", 1000000)

    # Initially disconnected
    assert not bus.is_connected()

    # Connect
    result = bus.connect()
    assert result is True
    assert bus.is_connected()

    # Disconnect
    result = bus.disconnect()
    assert result is True
    assert not bus.is_connected()


def test_motor_bus_context_manager() -> None:
    """Test MotorBus context manager."""
    mock_driver = Mock()
    mock_driver.connect.return_value = True

    with patch('leropilot.services.hardware.motor_drivers.feetech.drivers.FeetechDriver', return_value=mock_driver):
        bus = FeetechMotorBus("/dev/ttyUSB0", 1000000)

        with bus:
            assert bus.is_connected()

        assert not bus.is_connected()


def test_motor_bus_motor_registration() -> None:
    """Test motor registration with MotorBus."""
    bus = FeetechMotorBus("/dev/ttyUSB0", 1000000)

    # Create mock driver
    mock_driver = Mock()
    mock_driver.motor_id = 1

    # Register with explicit motor_id and MotorModelInfo as MotorBus.register_motor requires
    mi = MotorModelInfo(model="X", model_ids=[0], limits={}, brand=MotorBrand.FEETECH)
    bus.register_motor(1, mock_driver, mi)
    assert bus.get_motor(1) == mock_driver
    assert bus.get_motor(2) is None


def test_feetech_motor_bus_scan() -> None:
    """Test FeetechMotorBus scanning functionality."""
    bus = FeetechMotorBus("/dev/ttyUSB0", 1000000)

    # Test that scan returns empty when not connected
    assert not bus.is_connected()
    results = bus.scan_motors([1])
    assert len(results) == 0

    # Test that scan returns empty when connected but no driver class functionality
    bus.connect()
    assert bus.is_connected()
    results = bus.scan_motors([1])
    assert len(results) == 0


def test_batch_operations() -> None:
    """Test batch operations on MotorBus."""
    mock_driver1 = Mock()
    mock_driver1.motor_id = 1
    mock_driver2 = Mock()
    mock_driver2.motor_id = 2

    bus = FeetechMotorBus("/dev/ttyUSB0", 1000000)
    mi1 = MotorModelInfo(model="X", model_ids=[0], limits={}, brand=MotorBrand.FEETECH)
    mi2 = MotorModelInfo(model="X", model_ids=[0], limits={}, brand=MotorBrand.FEETECH)
    bus.register_motor(1, mock_driver1, mi1)
    bus.register_motor(2, mock_driver2, mi2)

    # Test batch read telemetry using read_bulk_telemetry
    mock_driver1.read_telemetry.return_value = Mock(position=100, velocity=0, current=50)
    mock_driver2.read_telemetry.return_value = Mock(position=200, velocity=0, current=60)

    results = bus.read_bulk_telemetry([1, 2])
    assert len(results) == 2
    assert results[1].position == 100
    assert results[2].position == 200

    # Test individual set position
    bus.set_position(1, 150)
    mock_driver1.set_position.assert_called_with(1, 150, None)
