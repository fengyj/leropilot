"""Test the new lerobot-inspired MotorBus architecture."""
from unittest.mock import Mock

import pytest

from leropilot.services.hardware.motor_buses.damiao_motor_bus import DamiaoMotorBus
from leropilot.services.hardware.motor_buses.dynamixel_motor_bus import DynamixelMotorBus
from leropilot.services.hardware.motor_buses.feetech_motor_bus import FeetechMotorBus
from leropilot.services.hardware.motor_buses.motor_bus import MotorBus
from leropilot.services.hardware.motor_drivers.feetech.drivers import FeetechDriver


class TestMotorBusArchitecture:
    """Test the new MotorBus architecture."""

    def test_abstract_motor_bus(self) -> None:
        """Test that MotorBus is abstract and cannot be instantiated directly."""
        with pytest.raises(TypeError):
            MotorBus("test", 1000000)

    def test_serial_motor_bus_creation(self) -> None:
        """Test SerialMotorBus can be created."""
        bus = FeetechMotorBus("/dev/ttyUSB0", 1000000)
        assert bus.interface == "/dev/ttyUSB0"
        assert bus.baud_rate == 1000000
        assert bus.driver_class == FeetechDriver
        assert not bus.is_connected()

    def test_can_motor_bus_creation(self) -> None:
        """Test CANMotorBus can be created."""
        bus = DamiaoMotorBus("can0", 1000000)
        assert bus.interface == "can0"
        assert bus.baud_rate == 1000000
        assert not bus.is_connected()

    def test_serial_motor_bus_scan(self) -> None:
        """Test SerialMotorBus scanning functionality."""
        # Create bus without driver class to test basic functionality
        bus = FeetechMotorBus("/dev/ttyUSB0", 1000000)

        # Test that scan returns empty when not connected
        assert not bus.is_connected()
        results = bus.scan_motors([1])
        assert len(results) == 0

        # Test that scan returns empty when no driver class
        bus.connect()
        assert bus.is_connected()
        results = bus.scan_motors([1])
        assert len(results) == 0

    def test_motor_bus_context_manager(self) -> None:
        """Test MotorBus context manager."""
        bus = FeetechMotorBus("/dev/ttyUSB0", 1000000)

        with bus:
            assert bus.is_connected()

        assert not bus.is_connected()

    def test_motorbus_factory(self) -> None:
        """Factory should construct the appropriate subclass from a string."""
        m1 = MotorBus.create("feetech", "/dev/ttyUSB0", 1000000)
        assert isinstance(m1, FeetechMotorBus)

        m2 = MotorBus.create("dynamixel", "/dev/ttyUSB0", 1000000)
        assert isinstance(m2, DynamixelMotorBus)

        m3 = MotorBus.create("damiao", "can0", 1000000)
        assert isinstance(m3, DamiaoMotorBus)

        # Accept class input too
        m4 = MotorBus.create(FeetechMotorBus, "/dev/ttyUSB0", 1000000)
        assert isinstance(m4, FeetechMotorBus)

    def test_motor_bus_motor_registration(self):
        """Test motor registration with MotorBus."""
        bus = FeetechMotorBus("/dev/ttyUSB0", 1000000,)

        # Create mock driver
        mock_driver = Mock()
        mock_driver.motor_id = 1

        # Register using explicit motor_id and MotorModelInfo
        from leropilot.models.hardware import MotorBrand, MotorModelInfo
        mi = MotorModelInfo(model="X", model_ids=[0], limits={}, brand=MotorBrand.FEETECH)
        bus.register_motor(1, mock_driver, mi)
        assert bus.get_motor(1) == mock_driver
        assert bus.get_motor(2) is None
