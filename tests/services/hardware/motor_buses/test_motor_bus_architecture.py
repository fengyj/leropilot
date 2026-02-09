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
        bus = DamiaoMotorBus("socketcan:can0", 1000000)
        assert bus.interface == "socketcan:can0"
        assert bus.baud_rate == 1000000
        assert not bus.is_connected()

    def test_serial_motor_bus_scan(self) -> None:
        """Test SerialMotorBus scanning functionality."""
        from unittest.mock import patch

        from leropilot.exceptions import OperationalError

        bus = FeetechMotorBus("/dev/ttyUSB0", 1000000)

        # Test that scan raises OperationalError when not connected
        assert not bus.is_connected()
        with pytest.raises(OperationalError):
            bus.scan_motors([1])

        # Test that scan works when connected with mocked driver
        with patch("leropilot.services.hardware.motor_buses.feetech_motor_bus.FeetechDriver") as MockDriver:
            mock_instance = Mock()
            mock_instance.connect.return_value = True
            mock_instance.scan_motors.return_value = {}  # Empty scan result
            MockDriver.return_value = mock_instance

            bus.connect()
            assert bus.is_connected()
            results = bus.scan_motors([1])
            assert len(results) == 0

    def test_motor_bus_context_manager(self) -> None:
        """Test MotorBus context manager."""
        from unittest.mock import patch

        with patch("leropilot.services.hardware.motor_buses.feetech_motor_bus.FeetechDriver") as MockDriver:
            mock_instance = Mock()
            mock_instance.connect.return_value = True
            mock_instance.disconnect.return_value = True
            MockDriver.return_value = mock_instance

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
        from unittest.mock import patch

        bus = FeetechMotorBus("/dev/ttyUSB0", 1000000)

        # Mock driver and connect to create shared driver
        from leropilot.models.hardware import MotorBrand, MotorModelInfo

        with patch("leropilot.services.hardware.motor_buses.feetech_motor_bus.FeetechDriver") as MockDriver:
            mock_instance = Mock()
            mock_instance.connect.return_value = True
            MockDriver.return_value = mock_instance

            bus.connect()

            # Register using only motor_info (driver is shared)
            mi = MotorModelInfo(
                model="X", model_ids=[0], limits={}, brand=MotorBrand.FEETECH, encoder_resolution=4096.0
            )
            bus.register_motor(1, mi)

            # Shared driver is available via bus.driver
            assert bus.driver is not None
            # Motor info can be retrieved
            assert bus.get_motor_info(1) == mi
            assert bus.get_motor_info(2) is None
