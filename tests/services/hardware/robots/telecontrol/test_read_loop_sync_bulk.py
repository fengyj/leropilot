import asyncio
import logging
from unittest.mock import MagicMock, Mock, patch

import pytest

from leropilot.models.hardware import (
    DeviceStatus,
    MotorBusDefinition,
    Robot,
    RobotDefinition,
    RobotMotorBusConnection,
    RobotMotorDefinition,
)
from leropilot.services.hardware.robots.telecontrol import RobotTelecontrolService


@pytest.fixture
def test_robot_single_bus():
    motor_def = RobotMotorDefinition(name="joint_1", id=1, brand="dynamixel", model="Test Motor")
    motor_bus_def = MotorBusDefinition(type="dynamixel", motors={"joint_1": motor_def}, baud_rate=1000000)

    robot_def = RobotDefinition(
        id="test_robot",
        lerobot_name="test_robot",
        display_name="Test Robot",
        description="Description",
        motor_buses={"motor_bus_1": motor_bus_def},
    )

    robot = Robot(
        id="test_robot_id",
        name="Test Robot",
        status=DeviceStatus.AVAILABLE,
        definition=robot_def,
        motor_bus_connections={
            "motor_bus_1": RobotMotorBusConnection(motor_bus_type="dynamixel", interface="/dev/null", baudrate=1000000)
        },
        calibration_settings={"motor_bus_1": []},
        is_calibrated=False,
    )
    return robot


@pytest.mark.asyncio
async def test_read_loop_handles_sync_bulk_read(test_robot_single_bus, caplog):
    """Ensure read loop works when MotorBus.bulk_read_telemetry is a synchronous function."""
    with patch("leropilot.services.hardware.robots.telecontrol.MotorBus") as mock_bus_class:
        mock_bus_instance = MagicMock()
        mock_bus_instance.connect = Mock()
        mock_bus_instance.disconnect = Mock()
        mock_bus_instance.motors = {1: MagicMock()}
        mock_bus_instance.scan_motors = Mock(return_value={1: MagicMock()})

        # synchronous bulk_read_telemetry implementation
        def sync_read(mids):
            return {1: MagicMock()}

        mock_bus_instance.bulk_read_telemetry = sync_read

        mock_bus_class.create.return_value = mock_bus_instance

        service = RobotTelecontrolService(test_robot_single_bus)

        with caplog.at_level(logging.INFO):
            await service.start(fps=20)
            await asyncio.sleep(0.2)
            await service.stop()

        # Ensure service started and stopped without TypeError
        assert not service._running
        assert service._read_task is None or service._read_task.done()
        # Ensure we observed read-loop start log
        assert any("Started motor telemetry read loop" in r.message for r in caplog.records)
