"""Unit tests for RobotTelecontrolService exception handling and callback isolation."""

import asyncio
import logging
import time
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from leropilot.models.hardware import (
    DeviceStatus,
    MotorBusDefinition,
    MotorTelemetry,
    PositionType,
    Robot,
    RobotDefinition,
    RobotMotorBusConnection,
    RobotMotorDefinition,
)
from leropilot.services.hardware.robots.telecontrol import RobotTelecontrolService


@pytest.fixture
def mock_robot_definition():
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
def test_robot(mock_robot_definition):
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
            "motor_bus_1": [],
        },
        is_calibrated=False,
    )
    return robot


@pytest.mark.asyncio
async def test_stop_captures_task_exception(test_robot, caplog):
    """Test that read loop handles exceptions gracefully and continues/stops properly."""
    with patch("leropilot.services.hardware.robots.telecontrol.MotorBus") as mock_bus_class:
        # Setup mock bus
        mock_bus_instance = MagicMock()
        mock_bus_instance.connect = Mock()
        mock_bus_instance.disconnect = Mock()
        mock_bus_instance.motors = {1: MagicMock()}
        mock_bus_instance.scan_motors = Mock(return_value={1: MagicMock()})

        # Make bulk_read_telemetry raise an exception
        error_msg = "Critical driver failure"
        mock_bus_instance.bulk_read_telemetry = AsyncMock(side_effect=RuntimeError(error_msg))

        mock_bus_class.create.return_value = mock_bus_instance

        service = RobotTelecontrolService(test_robot)

        # Capture logs from the telecontrol module
        with caplog.at_level(logging.WARNING, logger="leropilot.services.hardware.robots.telecontrol"):
            await service.start(fps=100)  # High FPS for quick failure
            await asyncio.sleep(0.3)  # Give it time to attempt reads
            await service.stop()

        # The service should handle exceptions gracefully
        # Verify service stopped cleanly without hanging
        assert not service._running
        assert service._read_task is None or service._read_task.done()


@pytest.mark.asyncio
async def test_sync_callback_does_not_block_event_loop(test_robot):
    """Test that synchronous callbacks are executed in thread pool and don't block event loop."""
    with patch("leropilot.services.hardware.robots.telecontrol.MotorBus") as mock_bus_class:
        # Setup mock bus
        mock_bus_instance = MagicMock()
        mock_bus_instance.connect = Mock()
        mock_bus_instance.disconnect = Mock()
        mock_bus_instance.motors = {1: MagicMock()}
        mock_bus_instance.scan_motors = Mock(return_value={1: MagicMock()})
        mock_bus_instance.bulk_read_telemetry = AsyncMock(
            return_value={
                1: MotorTelemetry(
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
            }
        )

        mock_bus_class.create.return_value = mock_bus_instance

        # Create a blocking sync callback
        callback_executed = []
        block_duration = 0.1  # 100ms blocking call

        def blocking_sync_callback(frame):
            """Simulates a slow synchronous callback (e.g., file I/O, network call)."""
            time.sleep(block_duration)
            callback_executed.append(time.time())

        service = RobotTelecontrolService(test_robot)

        # Start service with blocking callback
        start_time = time.time()
        await service.start(callback=blocking_sync_callback, fps=10)

        # Wait for at least 2-3 callbacks
        await asyncio.sleep(0.5)
        await service.stop()

        elapsed = time.time() - start_time

        # If callbacks were blocking the event loop, total time would be:
        # num_callbacks * block_duration = ~5 * 0.1 = 0.5s ADDED to normal operation
        # With executor, they run in parallel, so total time should be close to 0.5s

        # Verify callbacks were executed
        assert len(callback_executed) >= 2, "Expected multiple callbacks to execute"

        # Verify event loop wasn't blocked (total time should be ~0.5-0.7s, not >1s)
        assert elapsed < 1.0, f"Event loop appears blocked: elapsed={elapsed:.2f}s, callbacks={len(callback_executed)}"


@pytest.mark.asyncio
async def test_async_callback_exception_does_not_kill_loop(test_robot, caplog):
    """Test that exceptions in async callbacks are caught and logged without killing loop."""
    with patch("leropilot.services.hardware.robots.telecontrol.MotorBus") as mock_bus_class:
        # Setup mock bus
        mock_bus_instance = MagicMock()
        mock_bus_instance.connect = Mock()
        mock_bus_instance.disconnect = Mock()
        mock_bus_instance.motors = {1: MagicMock()}
        mock_bus_instance.scan_motors = Mock(return_value={1: MagicMock()})
        mock_bus_instance.bulk_read_telemetry = AsyncMock(
            return_value={
                1: MotorTelemetry(
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
            }
        )

        mock_bus_class.create.return_value = mock_bus_instance

        callback_count = [0]

        async def failing_callback(frame):
            """Callback that raises exception on first call, then succeeds."""
            callback_count[0] += 1
            if callback_count[0] == 1:
                raise ValueError("Intentional callback failure")

        service = RobotTelecontrolService(test_robot)

        with caplog.at_level(logging.WARNING):
            await service.start(callback=failing_callback, fps=20)
            await asyncio.sleep(0.3)  # Allow multiple callbacks
            await service.stop()

        # Verify loop continued after callback exception
        assert callback_count[0] > 1, "Loop should continue after callback exception"

        # Verify exception was logged
        assert any(
            "callback" in record.message.lower() and "error" in record.message.lower() for record in caplog.records
        ), "Expected callback exception to be logged"


@pytest.mark.asyncio
async def test_read_loop_handles_driver_exceptions_gracefully(test_robot, caplog):
    """Test that _read_loop handles driver exceptions without terminating."""
    with patch("leropilot.services.hardware.robots.telecontrol.MotorBus") as mock_bus_class:
        # Setup mock bus
        mock_bus_instance = MagicMock()
        mock_bus_instance.connect = Mock()
        mock_bus_instance.disconnect = Mock()
        mock_bus_instance.motors = {1: MagicMock()}
        mock_bus_instance.scan_motors = Mock(return_value={1: MagicMock()})

        # Make bulk_read_telemetry fail first 2 times, then succeed
        call_count = [0]

        async def flaky_read(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] <= 2:
                raise RuntimeError("Transient driver error")
            return {
                1: MotorTelemetry(
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
            }

        mock_bus_instance.bulk_read_telemetry = flaky_read

        mock_bus_class.create.return_value = mock_bus_instance

        service = RobotTelecontrolService(test_robot)

        with caplog.at_level(logging.WARNING):
            await service.start(fps=20)
            await asyncio.sleep(0.3)  # Allow recovery
            await service.stop()

        # Verify loop recovered and continued
        assert call_count[0] > 2, "Loop should continue after transient errors"

        # Verify errors were logged
        error_logs = [r for r in caplog.records if "error" in r.message.lower()]
        assert len(error_logs) >= 2, "Expected transient errors to be logged"


@pytest.mark.asyncio
async def test_read_loop_fatal_exception_stops_gracefully(test_robot, caplog):
    """Test that fatal exceptions immediately stop the service."""
    with patch("leropilot.services.hardware.robots.telecontrol.MotorBus") as mock_bus_class:
        # Setup mock bus
        mock_bus_instance = MagicMock()
        mock_bus_instance.connect = Mock()
        mock_bus_instance.disconnect = Mock()
        mock_bus_instance.motors = {1: MagicMock()}
        mock_bus_instance.scan_motors = Mock(return_value={1: MagicMock()})

        # Make bulk_read_telemetry raise a fatal exception (TypeError = driver API mismatch)
        async def fatal_error(*args, **kwargs):
            raise TypeError("Driver API signature mismatch - fatal error")

        mock_bus_instance.bulk_read_telemetry = fatal_error

        mock_bus_class.create.return_value = mock_bus_instance

        service = RobotTelecontrolService(test_robot)

        with caplog.at_level(logging.CRITICAL, logger="leropilot.services.hardware.robots.telecontrol"):
            await service.start(fps=50)
            await asyncio.sleep(0.3)
            await service.stop()

        # Verify fatal error was logged with CRITICAL level
        assert any("fatal" in record.message.lower() for record in caplog.records), (
            f"Expected fatal error to be logged. Records: {[r.message for r in caplog.records]}"
        )

        # Service should have stopped itself
        assert not service._running
        assert service._read_task is None or service._read_task.done()


@pytest.mark.asyncio
async def test_consecutive_errors_trigger_shutdown(test_robot, caplog):
    """Test that exceeding max consecutive errors stops the service."""
    with patch("leropilot.services.hardware.robots.telecontrol.MotorBus") as mock_bus_class:
        # Setup mock bus
        mock_bus_instance = MagicMock()
        mock_bus_instance.connect = Mock()
        mock_bus_instance.disconnect = Mock()
        mock_bus_instance.motors = {1: MagicMock()}
        mock_bus_instance.scan_motors = Mock(return_value={1: MagicMock()})

        # Make bulk_read_telemetry always raise a transient error (IOError)
        async def transient_error(*args, **kwargs):
            raise OSError("Persistent hardware communication failure")

        mock_bus_instance.bulk_read_telemetry = transient_error

        mock_bus_class.create.return_value = mock_bus_instance

        service = RobotTelecontrolService(test_robot)
        # Lower threshold for faster test
        service._max_consecutive_errors = 3

        with caplog.at_level(logging.CRITICAL, logger="leropilot.services.hardware.robots.telecontrol"):
            await service.start(fps=50)
            await asyncio.sleep(0.5)  # Allow multiple failures
            await service.stop()

        # Verify the service stopped itself after exceeding threshold
        assert any("exceeded max consecutive errors" in record.message.lower() for record in caplog.records), (
            f"Expected consecutive error threshold message. Records: {[r.message for r in caplog.records]}"
        )

        # Verify error counter reached threshold
        assert service._consecutive_errors >= 3


@pytest.mark.asyncio
async def test_successful_read_resets_error_counter(test_robot):
    """Test that successful reads reset the consecutive error counter."""
    with patch("leropilot.services.hardware.robots.telecontrol.MotorBus") as mock_bus_class:
        # Setup mock bus
        mock_bus_instance = MagicMock()
        mock_bus_instance.connect = Mock()
        mock_bus_instance.disconnect = Mock()
        mock_bus_instance.motors = {1: MagicMock()}
        mock_bus_instance.scan_motors = Mock(return_value={1: MagicMock()})

        # Alternate between failure and success
        call_count = [0]

        async def alternating_read(*args, **kwargs):
            call_count[0] += 1
            # Fail on odd calls, succeed on even calls
            if call_count[0] % 2 == 1:
                raise OSError("Transient error")
            return {
                1: MotorTelemetry(
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
            }

        mock_bus_instance.bulk_read_telemetry = alternating_read

        mock_bus_class.create.return_value = mock_bus_instance

        service = RobotTelecontrolService(test_robot)

        await service.start(fps=30)
        await asyncio.sleep(0.5)  # Allow multiple cycles
        await service.stop()

        # Verify error counter was reset (never exceeded 1)
        assert service._consecutive_errors <= 1, (
            f"Error counter should reset after success, but got {service._consecutive_errors}"
        )
