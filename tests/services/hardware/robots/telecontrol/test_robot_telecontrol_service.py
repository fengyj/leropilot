"""Unit tests for RobotTelecontrolService."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from leropilot.exceptions import OperationalError
from leropilot.models.hardware import (
    DeviceStatus,
    MotorBrand,
    MotorBusDefinition,
    MotorCalibration,
    MotorModelInfo,
    MotorTelemetry,
    PositionType,
    Robot,
    RobotDefinition,
    RobotMotorBusConnection,
    RobotMotorDefinition,
)
from leropilot.services.hardware.robots.telecontrol import RobotTelecontrolService

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_motor_model_info():
    """Create a mock MotorModelInfo."""
    return MotorModelInfo(
        model="Test Motor",
        model_ids=[1],
        limits={},
        brand=MotorBrand.DYNAMIXEL,
        position_scale=1.0,
        encoder_resolution=4096.0,
    )


@pytest.fixture
def mock_motor_calibration():
    """Create a mock MotorCalibration."""
    return MotorCalibration(
        name="joint_1",
        id=1,
        drive_mode=0,
        homing_offset=0,
        range_min=-100,
        range_max=100,
        soft_homing_offset=False,
    )


@pytest.fixture
def mock_robot_definition(mock_motor_model_info):
    """Create a mock RobotDefinition."""
    motor_def = RobotMotorDefinition(
        name="joint_1",
        id=1,
        brand="dynamixel",
        model="Test Motor",
    )

    motor_bus_def = MotorBusDefinition(
        type="dynamixel",
        motors={"joint_1": motor_def},
        baud_rate=1000000,
    )

    return RobotDefinition(
        id="test_robot",
        lerobot_name="test_robot",
        display_name="Test Robot",
        description="Test robot for unit tests",
        motor_buses={"motor_bus_1": motor_bus_def},
    )


@pytest.fixture
def test_robot(mock_robot_definition, mock_motor_calibration):
    """Create a test robot with AVAILABLE status."""
    robot = Robot(
        id="test_robot_id",
        name="Test Robot",
        status=DeviceStatus.AVAILABLE,
        definition=mock_robot_definition,
        motor_bus_connections={
            "motor_bus_1": RobotMotorBusConnection(
                motor_bus_type="dynamixel",
                interface="/dev/ttyUSB0",
                baudrate=1000000,
            )
        },
        calibration_settings={
            "motor_bus_1": [mock_motor_calibration],
        },
        is_calibrated=False,
    )
    return robot


# ============================================================================
# Tests: Initialization and State Validation
# ============================================================================


def test_init_robot_not_available():
    """Test that init raises OperationalError when robot status is not AVAILABLE."""
    robot = Robot(
        id="test_id",
        name="Test",
        status=DeviceStatus.OFFLINE,
        is_calibrated=False,
    )
    with pytest.raises(OperationalError):
        RobotTelecontrolService(robot)


def test_init_motor_bus_no_interface():
    """Test that init raises OperationalError when motor bus has no interface."""
    robot = Robot(
        id="test_id",
        name="Test",
        status=DeviceStatus.AVAILABLE,
        motor_bus_connections={
            "bus1": RobotMotorBusConnection(
                motor_bus_type="dynamixel",
                interface=None,
                baudrate=1000000,
            )
        },
        is_calibrated=False,
    )
    with pytest.raises(OperationalError):
        RobotTelecontrolService(robot)


@pytest.mark.asyncio
async def test_async_context_manager(test_robot):
    """Test that service works as async context manager."""
    with patch("leropilot.services.hardware.robots.telecontrol.MotorBus") as mock_bus_class:
        mock_bus_instance = MagicMock()
        mock_bus_instance.connect = Mock()
        mock_bus_instance.disconnect = Mock()
        mock_bus_instance.motors = {1: MagicMock()}
        mock_bus_instance.scan_motors = Mock(return_value={1: MagicMock()})
        mock_bus_class.create.return_value = mock_bus_instance

        async with RobotTelecontrolService(test_robot) as service:
            assert service._robot == test_robot
            # Need to start service for disconnect to be called
            await service.start()

        # Verify stop was called (via __aexit__)
        mock_bus_instance.disconnect.assert_called()


# ============================================================================
# Tests: Start/Stop and Motor Bus Initialization
# ============================================================================


@pytest.mark.asyncio
async def test_start_initializes_motor_buses(test_robot):
    """Test that start() initializes motor buses correctly."""
    with (
        patch("leropilot.services.hardware.robots.telecontrol.MotorBus") as mock_bus_class,
        patch("leropilot.services.hardware.robots.telecontrol.CalibrationService"),
    ):
        mock_bus_instance = MagicMock()
        mock_bus_instance.connect = Mock()
        mock_bus_instance.disconnect = Mock()
        mock_bus_instance.motors = {}
        mock_bus_instance.scan_motors = Mock(return_value={1: MagicMock()})
        mock_bus_instance.calibrations = {}
        # Add async mock for bulk_read_telemetry
        mock_bus_instance.bulk_read_telemetry = AsyncMock(return_value={})
        mock_bus_class.create.return_value = mock_bus_instance

        service = RobotTelecontrolService(test_robot)
        start_task = asyncio.create_task(service.start())
        await asyncio.sleep(0.1)  # Let start initialize

        assert service._running
        assert "motor_bus_1" in service._motor_buses
        mock_bus_class.create.assert_called_once()
        mock_bus_instance.connect.assert_called_once()

        await service.stop()
        await start_task


@pytest.mark.asyncio
async def test_stop_disconnects_buses(test_robot):
    """Test that stop() disconnects all motor buses."""
    with (
        patch("leropilot.services.hardware.robots.telecontrol.MotorBus") as mock_bus_class,
        patch("leropilot.services.hardware.robots.telecontrol.CalibrationService"),
    ):
        mock_bus_instance = MagicMock()
        mock_bus_instance.connect = Mock()
        mock_bus_instance.disconnect = Mock()
        mock_bus_instance.motors = {}
        mock_bus_instance.scan_motors = Mock(return_value={})
        mock_bus_class.create.return_value = mock_bus_instance

        service = RobotTelecontrolService(test_robot)
        await service.start()
        await service.stop()

        mock_bus_instance.disconnect.assert_called()


# ============================================================================
# Tests: Motor Operations
# ============================================================================


@pytest.mark.asyncio
async def test_emergency_stop(test_robot):
    """Test emergency_stop() disables all motors."""
    with (
        patch("leropilot.services.hardware.robots.telecontrol.MotorBus") as mock_bus_class,
        patch("leropilot.services.hardware.robots.telecontrol.CalibrationService"),
    ):
        mock_bus_instance = MagicMock()
        mock_bus_instance.connect = Mock()
        mock_bus_instance.disconnect = Mock()
        mock_bus_instance.motors = {1: MagicMock()}
        mock_bus_instance.scan_motors = Mock(return_value={1: MagicMock()})
        mock_bus_instance.set_torque = Mock(return_value=True)
        mock_bus_class.create.return_value = mock_bus_instance

        service = RobotTelecontrolService(test_robot)
        await service.start()
        await service.emergency_stop()

        # Verify set_torque(False) was called for each motor
        assert mock_bus_instance.set_torque.call_count >= 1
        mock_bus_instance.set_torque.assert_called_with(1, False)

        await service.stop()


@pytest.mark.asyncio
async def test_set_positions(test_robot):
    """Test set_positions() sends position commands to motors."""
    with (
        patch("leropilot.services.hardware.robots.telecontrol.MotorBus") as mock_bus_class,
        patch("leropilot.services.hardware.robots.telecontrol.CalibrationService"),
    ):
        mock_bus_instance = MagicMock()
        mock_bus_instance.connect = Mock()
        mock_bus_instance.disconnect = Mock()
        mock_bus_instance.motors = {1: MagicMock()}
        mock_bus_instance.scan_motors = Mock(return_value={1: MagicMock()})
        mock_bus_instance.set_position = Mock(return_value=True)
        mock_bus_class.create.return_value = mock_bus_instance

        service = RobotTelecontrolService(test_robot)
        await service.start()
        # Use bus_name and motor_name from robot definition
        await service.set_positions({"motor_bus_1": {"joint_1": 0.5}})

        mock_bus_instance.set_position.assert_called()
        await service.stop()


@pytest.mark.asyncio
async def test_set_torques(test_robot):
    """Test set_torques() enables/disables motor torques."""
    with (
        patch("leropilot.services.hardware.robots.telecontrol.MotorBus") as mock_bus_class,
        patch("leropilot.services.hardware.robots.telecontrol.CalibrationService"),
    ):
        mock_bus_instance = MagicMock()
        mock_bus_instance.connect = Mock()
        mock_bus_instance.disconnect = Mock()
        mock_bus_instance.motors = {1: MagicMock()}
        mock_bus_instance.scan_motors = Mock(return_value={1: MagicMock()})
        mock_bus_instance.set_torque = Mock(return_value=True)
        mock_bus_class.create.return_value = mock_bus_instance

        service = RobotTelecontrolService(test_robot)
        await service.start()
        # Use bus_name and motor_name from robot definition
        await service.set_torques({"motor_bus_1": {"joint_1": True}})

        mock_bus_instance.set_torque.assert_called_with(1, True)
        await service.stop()


# ============================================================================
# Tests: Polling Control
# ============================================================================


@pytest.mark.asyncio
async def test_polling_enabled_disabled(test_robot):
    """Test polling(enabled) controls telemetry streaming."""
    with (
        patch("leropilot.services.hardware.robots.telecontrol.MotorBus") as mock_bus_class,
        patch("leropilot.services.hardware.robots.telecontrol.CalibrationService"),
    ):
        mock_bus_instance = MagicMock()
        mock_bus_instance.connect = Mock()
        mock_bus_instance.disconnect = Mock()
        mock_bus_instance.motors = {1: MagicMock()}
        mock_bus_instance.scan_motors = Mock(return_value={1: MagicMock()})
        mock_bus_instance.bulk_read_telemetry = Mock(return_value={})
        mock_bus_class.create.return_value = mock_bus_instance

        service = RobotTelecontrolService(test_robot)
        await service.start()

        # Disable polling
        await service.polling(False)
        assert not service._polling_event.is_set()

        # Enable polling
        await service.polling(True)
        assert service._polling_event.is_set()

        await service.stop()


# ============================================================================
# Tests: FPS Calculation
# ============================================================================


@pytest.mark.asyncio
async def test_fps_calculation():
    """Test that actual FPS is calculated correctly as integer."""
    service = RobotTelecontrolService.__new__(RobotTelecontrolService)
    service._timestamp_deque = __import__("collections").deque()
    service._actual_fps = 0
    service._target_fps = 30

    # Simulate adding timestamps at ~30 Hz
    base_time = 1000.0
    for i in range(65):  # 65 samples at 30Hz = ~2.17 seconds
        service._update_fps(base_time + i / 30.0)

    # FPS should be integer and close to 30
    assert isinstance(service._actual_fps, int), f"FPS should be int, got {type(service._actual_fps)}"
    assert 25 < service._actual_fps < 35, f"FPS {service._actual_fps} not close to 30"


# ============================================================================
# Tests: Homing Offset and Range Setting
# ============================================================================


@pytest.mark.asyncio
async def test_set_homing_offsets(test_robot):
    """Test set_homing_offsets() updates calibration data."""
    with (
        patch("leropilot.services.hardware.robots.telecontrol.MotorBus") as mock_bus_class,
        patch("leropilot.services.hardware.robots.telecontrol.CalibrationService"),
    ):
        mock_bus_instance = MagicMock()
        mock_bus_instance.connect = Mock()
        mock_bus_instance.disconnect = Mock()
        mock_bus_instance.motors = {1: MagicMock()}
        mock_bus_instance.scan_motors = Mock(return_value={1: MagicMock()})
        mock_bus_instance.read_telemetry = Mock(
            return_value=MotorTelemetry(
                id=1,
                position=50.0,
                position_type=PositionType.RAW,
                velocity=0.0,
                current=0,
                load=0,
                temperature=0,
                voltage=0.0,
                moving=False,
            )
        )
        mock_bus_instance.register_calibration = Mock()
        mock_bus_class.create.return_value = mock_bus_instance

        service = RobotTelecontrolService(test_robot)
        await service.start()
        total = await service.set_homing_offsets()

        assert total == 1
        mock_bus_instance.register_calibration.assert_called()
        await service.stop()


@pytest.mark.asyncio
async def test_set_ranges(test_robot):
    """Test set_ranges() updates position ranges."""
    with (
        patch("leropilot.services.hardware.robots.telecontrol.MotorBus") as mock_bus_class,
        patch("leropilot.services.hardware.robots.telecontrol.CalibrationService"),
    ):
        mock_bus_instance = MagicMock()
        mock_bus_instance.connect = Mock()
        mock_bus_instance.disconnect = Mock()
        mock_bus_instance.motors = {1: MagicMock()}
        mock_bus_instance.scan_motors = Mock(return_value={1: MagicMock()})
        mock_bus_instance.register_calibration = Mock()
        mock_bus_class.create.return_value = mock_bus_instance

        service = RobotTelecontrolService(test_robot)
        await service.start()
        await service.set_ranges({1: {"range_min": -100, "range_max": 100}})

        mock_bus_instance.register_calibration.assert_called()
        await service.stop()
