"""Tests for MotorBus implementation."""

from unittest.mock import Mock, patch

import pytest

from leropilot.models.hardware import MotorBrand, MotorCalibration, MotorModelInfo, MotorNormMode, PositionType
from leropilot.services.hardware.motor_buses.damiao_motor_bus import DamiaoMotorBus
from leropilot.services.hardware.motor_buses.feetech_motor_bus import FeetechMotorBus
from leropilot.services.hardware.motor_buses.motor_bus import MotorBus
from leropilot.services.hardware.motor_drivers.base import BaseMotorDriver
from leropilot.services.hardware.motor_drivers.feetech.drivers import FeetechDriver


def _make_mi(
    model: str = "X",
    model_ids: list = None,
    brand: MotorBrand = MotorBrand.FEETECH,
    encoder_resolution: float = 4096.0,
    position_to_radian_ratio: float = 1.0,
    velocity_ratio: float = 1.0,
    current_unit_ma_per_bit: float = 1.0,
    voltage_unit_v_per_bit: float = 1.0,
    temperature_unit_c_per_bit: float = 1.0,
    **kwargs,
) -> MotorModelInfo:
    """Create a MotorModelInfo with sensible test defaults."""
    return MotorModelInfo(
        model=model,
        model_ids=model_ids or [0],
        limits={},
        brand=brand,
        encoder_resolution=encoder_resolution,
        position_to_radian_ratio=position_to_radian_ratio,
        velocity_ratio=velocity_ratio,
        current_unit_ma_per_bit=current_unit_ma_per_bit,
        voltage_unit_v_per_bit=voltage_unit_v_per_bit,
        temperature_unit_c_per_bit=temperature_unit_c_per_bit,
        **kwargs,
    )


class MockDriver(BaseMotorDriver):
    """Mock driver for testing."""

    def __init__(self, interface: str, baud_rate: int = 1000000):
        super().__init__(interface, baud_rate)
        self.connected = False

    def connect(self) -> bool:
        self.connected = True
        return True

    def disconnect(self) -> bool:
        self.connected = False
        return True

    def scan_motors(self, scan_range=None):
        return {}

    def read_telemetry(self, motor_id: int):
        from leropilot.models.hardware import MotorTelemetry, PositionType

        return MotorTelemetry(
            id=motor_id,
            position=motor_id * 100,
            position_type=PositionType.RAW,
            velocity=0,
            current=50,
            load=0,
            temperature=25.0,
            voltage=12.0,
            moving=False,
            error=0,
        )

    def bulk_read_telemetry(self, motor_ids: list[int]):
        from leropilot.models.hardware import MotorTelemetry, PositionType

        return {
            mid: MotorTelemetry(
                id=mid,
                position=mid * 100,
                position_type=PositionType.RAW,
                velocity=0,
                current=50 + mid,
                load=0,
                temperature=25.0,
                voltage=12.0,
                moving=False,
                goal_position=0,
                error=0,
            )
            for mid in motor_ids
        }

    def set_position(self, motor_id: int, position: int, speed=None) -> bool:
        return True

    def set_torque(self, motor_id: int, enabled: bool) -> bool:
        return True

    def bulk_set_torque(self, motor_ids: list[int], enabled: bool) -> bool:
        return True

    def identify_model(self, motor_id: int, model_number=None, fw_major=None, fw_minor=None, raise_on_ambiguous=False):
        return _make_mi(model="Mock")

    def supported_models(self):
        return [_make_mi(model="Mock")]

    def is_connected(self) -> bool:
        return self.connected


def test_abstract_motor_bus() -> None:
    """Test that MotorBus is abstract and cannot be instantiated directly."""
    with pytest.raises(TypeError):
        MotorBus()


def test_feetech_motor_bus_initialization() -> None:
    """Test FeetechMotorBus can be initialized without connection params."""
    bus = FeetechMotorBus()

    assert bus.interface is None
    assert bus.baud_rate is None
    assert bus.driver_class == FeetechDriver
    assert not bus.is_connected()


def test_damiao_motor_bus_initialization() -> None:
    """Test DamiaoMotorBus can be initialized without connection params."""
    bus = DamiaoMotorBus()

    assert bus.interface is None
    assert bus.baud_rate is None
    assert not bus.is_connected()


def test_feetech_motor_bus_connect_disconnect() -> None:
    """Test FeetechMotorBus connect/disconnect lifecycle."""
    bus = FeetechMotorBus()

    # Initially disconnected
    assert not bus.is_connected()

    # Mock the driver to avoid real hardware
    with patch("leropilot.services.hardware.motor_buses.feetech_motor_bus.FeetechDriver") as MockDriver:
        mock_instance = Mock()
        mock_instance.connect.return_value = True
        mock_instance.disconnect.return_value = True
        MockDriver.return_value = mock_instance

        # Connect
        bus.connect("/dev/ttyUSB0", 1000000)
        assert bus.is_connected()
        assert bus.driver is not None

        # Disconnect
        bus.disconnect()
        assert not bus.is_connected()
        assert bus.driver is None


def test_motor_bus_context_manager() -> None:
    """Test MotorBus context manager auto-disconnects on exit."""
    mock_instance = Mock()
    mock_instance.connect.return_value = True
    mock_instance.disconnect.return_value = True

    with patch("leropilot.services.hardware.motor_buses.feetech_motor_bus.FeetechDriver", return_value=mock_instance):
        bus = FeetechMotorBus()
        bus.connect("/dev/ttyUSB0", 1000000)

        with bus:
            assert bus.is_connected()
            assert bus.driver is not None

        assert not bus.is_connected()
        assert bus.driver is None


def test_motor_bus_motor_registration() -> None:
    """Test motor registration with MotorBus."""
    bus = FeetechMotorBus()

    # Mock driver and connect
    with patch("leropilot.services.hardware.motor_buses.feetech_motor_bus.FeetechDriver") as MockDriver:
        mock_instance = Mock()
        mock_instance.connect.return_value = True
        MockDriver.return_value = mock_instance

        bus.connect("/dev/ttyUSB0", 1000000)  # Need to connect first to create shared driver

        # Register motors with motor_info only (driver is shared)
        mi = MotorModelInfo(
            model="X",
            model_ids=[0],
            limits={},
            brand=MotorBrand.FEETECH,
            encoder_resolution=4096.0,
            position_to_radian_ratio=1.0,
            velocity_ratio=1.0,
            current_unit_ma_per_bit=1.0,
            voltage_unit_v_per_bit=1.0,
            temperature_unit_c_per_bit=1.0,
        )
        bus.register_motor(1, mi)

        # Verify motor info is stored
        assert bus.get_motor_info(1) == mi
        assert bus.get_motor_info(2) is None


def test_feetech_motor_bus_scan() -> None:
    """Test FeetechMotorBus scanning functionality."""
    bus = FeetechMotorBus()

    # Test that scan raises OperationalError when not connected
    assert not bus.is_connected()
    from leropilot.exceptions import OperationalError

    with pytest.raises(OperationalError):
        bus.scan_motors([1])

    # Test that scan works when connected with mocked driver
    with patch("leropilot.services.hardware.motor_buses.feetech_motor_bus.FeetechDriver") as MockDriver:
        mock_instance = Mock()
        mock_instance.connect.return_value = True
        mock_instance.scan_motors.return_value = {}  # Empty scan result
        MockDriver.return_value = mock_instance

        bus.connect("/dev/ttyUSB0", 1000000)
        assert bus.is_connected()
        results = bus.scan_motors([1])
        assert len(results) == 0

        # Verify driver's scan was called
        mock_instance.scan_motors.assert_called_once_with([1])


def test_batch_operations() -> None:
    """Test batch operations on MotorBus."""
    bus = FeetechMotorBus()

    # Mock driver class during connect
    with patch("leropilot.services.hardware.motor_buses.feetech_motor_bus.FeetechDriver") as MockDriver:
        mock_driver = Mock()
        mock_driver.connect.return_value = True
        mock_driver.bulk_read_telemetry.return_value = {
            1: Mock(position=100, velocity=0, current=51),
            2: Mock(position=200, velocity=0, current=52),
        }
        MockDriver.return_value = mock_driver

        # Connect
        bus.connect("/dev/ttyUSB0", 1000000)

        # Register motors
        mi1 = _make_mi()
        mi2 = _make_mi()
        bus.register_motor(1, mi1)
        bus.register_motor(2, mi2)

        # Test batch read telemetry using bulk_read_telemetry
        results = bus.bulk_read_telemetry([1, 2])
        assert len(results) == 2
        assert results[1].position == 100
        assert results[2].position == 200

        # Verify it called the driver's bulk method (not individual reads)
        mock_driver.bulk_read_telemetry.assert_called_once_with({1: mi1, 2: mi2})

        # Test individual set goal position (raw, identity conversion)
        bus.set_goal_position(1, 150)
        mock_driver.set_goal_position.assert_called_with(motor_id=1, position=150)


def test_bulk_set_goal_positions() -> None:
    """Test bulk_set_goal_positions API."""
    bus = FeetechMotorBus()

    # Mock driver class during connect
    with patch("leropilot.services.hardware.motor_buses.feetech_motor_bus.FeetechDriver") as MockDriver:
        mock_driver = Mock()
        mock_driver.connect.return_value = True
        MockDriver.return_value = mock_driver

        # Connect
        bus.connect("/dev/ttyUSB0", 1000000)

        # Register motors
        mi1 = _make_mi()
        mi2 = _make_mi()
        bus.register_motor(1, mi1)
        bus.register_motor(2, mi2)

        # Test bulk set goal positions (RAW input -> identity conversion -> driver)
        positions = {1: 1024.0, 2: 2048.0}
        bus.bulk_set_goal_positions(positions)

        # Verify driver method was called with unchanged raw values
        mock_driver.bulk_set_goal_positions.assert_called_once_with(motor_positions={1: 1024.0, 2: 2048.0})


def _make_connected_feetech_bus():
    from unittest.mock import Mock, patch

    bus = FeetechMotorBus()
    with patch("leropilot.services.hardware.motor_buses.feetech_motor_bus.FeetechDriver") as MockDriver:
        mock_driver = Mock()
        mock_driver.connect.return_value = True
        MockDriver.return_value = mock_driver
        bus.connect("/dev/ttyUSB0", 1000000)
    return bus


def test_normalized_to_calibrated_range_m100_100():
    bus = _make_connected_feetech_bus()

    # Register motor and calibration
    mi = _make_mi()
    bus.register_motor(1, mi)

    # Normal range 0..4095
    cal = MotorCalibration(
        name="j1",
        id=1,
        drive_mode=0,
        norm_mode=MotorNormMode.RANGE_M100_100,
        homing_offset=0,
        range_min=0,
        range_max=4095,
        soft_homing_offset=False,
    )
    bus.register_calibration(1, cal)

    # -1 -> min, 0 -> mid, 1 -> max
    assert bus._position_converter_cache.convert(
        1, PositionType.NORMALIZED, PositionType.CALIBRATED, -1.0
    ) == pytest.approx(0.0)
    assert bus._position_converter_cache.convert(
        1, PositionType.NORMALIZED, PositionType.CALIBRATED, 1.0
    ) == pytest.approx(4095.0)
    assert bus._position_converter_cache.convert(
        1, PositionType.NORMALIZED, PositionType.CALIBRATED, 0.0
    ) == pytest.approx(2047.5)


def test_converter_cache_reuse_and_conversion():
    bus = _make_connected_feetech_bus()

    mi = _make_mi()
    bus.register_motor(10, mi)

    cal = MotorCalibration(
        name="j10",
        id=10,
        drive_mode=0,
        norm_mode=MotorNormMode.RANGE_M100_100,
        homing_offset=0,
        range_min=0,
        range_max=4095,
        soft_homing_offset=False,
    )
    bus.register_calibration(10, cal)

    # Perform normalized -> RAW conversion twice and ensure same converter cached
    v1 = bus._position_converter_cache.convert(10, PositionType.NORMALIZED, PositionType.RAW, 0.0)
    v2 = bus._position_converter_cache.convert(10, PositionType.NORMALIZED, PositionType.RAW, 1.0)
    assert v1 == pytest.approx(2047.5)
    assert v2 == pytest.approx(4095.0)

    # Validate the converter object is cached (internal detail exposed for testing)
    key = (10, PositionType.NORMALIZED, PositionType.RAW)
    assert key in bus._position_converter_cache._cache
    conv_a = bus._position_converter_cache._cache[key]
    conv_b = bus._position_converter_cache._cache[key]
    assert conv_a is conv_b


def test_velocity_converter_cache_reuse_and_conversion():
    bus = _make_connected_feetech_bus()

    # velocity_ratio = 2.0 -> raw 10 -> rad/s 20.0
    mi = _make_mi(velocity_ratio=2.0)
    bus.register_motor(20, mi)

    cal = MotorCalibration(
        name="j20",
        id=20,
        drive_mode=0,
        norm_mode=MotorNormMode.RANGE_M100_100,
        homing_offset=0,
        range_min=0,
        range_max=4095,
        soft_homing_offset=False,
    )
    bus.register_calibration(20, cal)

    assert bus._velocity_converter_cache.raw_to_rad(20, 10) == pytest.approx(20.0)
    assert bus._velocity_converter_cache.rad_to_raw(20, 20.0) == pytest.approx(10.0)

    # cached objects (internal cache keyed by motor_id)
    assert 20 in bus._velocity_converter_cache._cache
    pair = bus._velocity_converter_cache._cache[20]
    assert pair[0](10) == pytest.approx(bus._velocity_converter_cache.raw_to_rad(20, 10))
    assert pair[1](20.0) == pytest.approx(bus._velocity_converter_cache.rad_to_raw(20, 20.0))


def test_velocity_converter_respects_drive_mode_inversion():
    bus = _make_connected_feetech_bus()

    # velocity_ratio = 2.0 -> raw 10 -> rad/s 20.0 normally
    mi = _make_mi(velocity_ratio=2.0)
    bus.register_motor(21, mi)

    # drive_mode=1 should invert the sign on conversions
    cal = MotorCalibration(
        name="j21",
        id=21,
        drive_mode=1,
        norm_mode=MotorNormMode.RANGE_M100_100,
        homing_offset=0,
        range_min=0,
        range_max=4095,
        soft_homing_offset=False,
    )
    bus.register_calibration(21, cal)

    # raw 10 -> rad should be -20.0 due to inversion
    assert bus._velocity_converter_cache.raw_to_rad(21, 10) == pytest.approx(-20.0)
    # rad 20.0 -> raw should be -10.0 due to inversion
    assert bus._velocity_converter_cache.rad_to_raw(21, 20.0) == pytest.approx(-10.0)


def test_normalized_to_calibrated_range_0_100_with_drive_mode_inversion():
    bus = _make_connected_feetech_bus()

    mi = _make_mi()
    bus.register_motor(2, mi)

    # drive_mode=1 should invert mapping
    cal = MotorCalibration(
        name="j2",
        id=2,
        drive_mode=1,
        norm_mode=MotorNormMode.RANGE_0_100,
        homing_offset=0,
        range_min=0,
        range_max=4095,
        soft_homing_offset=False,
    )
    bus.register_calibration(2, cal)

    # For RANGE_0_100 with drive_mode=1: normalized 1.0 -> percent -> (100 - percent) -> should map to min
    assert bus._position_converter_cache.convert(
        2, PositionType.NORMALIZED, PositionType.CALIBRATED, 1.0
    ) == pytest.approx(0.0)
    # normalized -1.0 -> percent 0 -> inverted to 100 -> maps to max
    assert bus._position_converter_cache.convert(
        2, PositionType.NORMALIZED, PositionType.CALIBRATED, -1.0
    ) == pytest.approx(4095.0)


def test_normalized_to_calibrated_degrees_mode():
    bus = _make_connected_feetech_bus()

    mi = _make_mi()
    bus.register_motor(3, mi)

    cal = MotorCalibration(
        name="j3",
        id=3,
        drive_mode=0,
        norm_mode=MotorNormMode.DEGREES,
        homing_offset=0,
        range_min=0,
        range_max=4095,
        soft_homing_offset=False,
    )
    bus.register_calibration(3, cal)

    # normalized 1.0 corresponds to +180 degrees -> should map near range_max
    val = bus._position_converter_cache.convert(3, PositionType.NORMALIZED, PositionType.CALIBRATED, 1.0)
    assert val == pytest.approx(4095.0, rel=1e-6)
    # normalized -1.0 corresponds to -180 degrees -> near range_min
    val2 = bus._position_converter_cache.convert(3, PositionType.NORMALIZED, PositionType.CALIBRATED, -1.0)
    assert val2 == pytest.approx(0.0, rel=1e-6)


def test_radian_to_raw_and_calibrated_conversion_with_soft_offset():
    bus = _make_connected_feetech_bus()

    # position_to_radian_ratio = 1.0 for simplicity
    mi = _make_mi()
    bus.register_motor(4, mi)

    cal = MotorCalibration(
        name="j4",
        id=4,
        drive_mode=0,
        norm_mode=MotorNormMode.RANGE_M100_100,
        homing_offset=5.0,
        range_min=0,
        range_max=4095,
        soft_homing_offset=True,
    )
    bus.register_calibration(4, cal)

    rad = 2.0
    # raw conversion is pure unit conversion (RAW_IN_RADIAN -> RAW)
    assert bus._position_converter_cache.convert(4, PositionType.RAW_IN_RADIAN, PositionType.RAW, rad) == pytest.approx(
        2.0
    )
    # converting CALIBRATED_IN_RADIAN -> RAW should apply homing offset when soft_homing_offset=True
    raw_conv = bus._position_converter_cache.convert(4, PositionType.CALIBRATED_IN_RADIAN, PositionType.RAW, rad)
    assert raw_conv == pytest.approx(7.0)


def test_conversion_lookup_table_routes_via_raw():
    bus = _make_connected_feetech_bus()

    mi = _make_mi()
    bus.register_motor(6, mi)

    cal = MotorCalibration(
        name="j6",
        id=6,
        drive_mode=0,
        norm_mode=MotorNormMode.RANGE_M100_100,
        homing_offset=0,
        range_min=0,
        range_max=4095,
        soft_homing_offset=False,
    )
    bus.register_calibration(6, cal)

    # normalized -> calibrated (via lookup table intermediate -> RAW routing)
    val = bus._position_converter_cache.convert(6, PositionType.NORMALIZED, PositionType.CALIBRATED, 0.0)
    # normalized 0.0 corresponds to mid = 2047.5
    assert val == pytest.approx(2047.5)


def test_radian_to_raw_and_calibrated_conversion_no_soft_offset():
    bus = _make_connected_feetech_bus()

    mi = _make_mi()
    bus.register_motor(5, mi)

    cal = MotorCalibration(
        name="j5",
        id=5,
        drive_mode=0,
        norm_mode=MotorNormMode.RANGE_M100_100,
        homing_offset=5.0,
        range_min=0,
        range_max=4095,
        soft_homing_offset=False,
    )
    bus.register_calibration(5, cal)

    rad = 2.0
    # raw conversion is pure unit conversion (RAW_IN_RADIAN -> RAW)
    assert bus._position_converter_cache.convert(5, PositionType.RAW_IN_RADIAN, PositionType.RAW, rad) == pytest.approx(
        2.0
    )
    # converting CALIBRATED_IN_RADIAN -> RAW should NOT apply homing offset when soft_homing_offset=False
    raw_conv = bus._position_converter_cache.convert(5, PositionType.CALIBRATED_IN_RADIAN, PositionType.RAW, rad)
    assert raw_conv == pytest.approx(2.0)


def test_motor_bus_errors_on_failure() -> None:
    """Test that MotorBus handles driver failures appropriately."""
    bus = FeetechMotorBus()
    from leropilot.exceptions import OperationalError

    with patch("leropilot.services.hardware.motor_buses.feetech_motor_bus.FeetechDriver") as MockDriver:
        mock_driver = Mock()
        mock_driver.connect.return_value = True
        mock_driver.read_telemetry.return_value = None
        MockDriver.return_value = mock_driver

        bus.connect("/dev/ttyUSB0", 1000000)
        bus.register_motor(1, Mock(brand=MotorBrand.FEETECH))
        bus.register_motor(2, Mock(brand=MotorBrand.FEETECH))

        # Test individual read_telemetry failure raises exception
        with pytest.raises(OperationalError) as excinfo:
            bus.read_telemetry(1)
        assert excinfo.value.i18n_key == "hardware.motor_device.read_failed"
        assert excinfo.value.params["motor_id"] == "1"
