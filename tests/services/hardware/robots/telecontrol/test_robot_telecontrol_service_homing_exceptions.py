from unittest.mock import MagicMock, Mock, patch

import pytest

from leropilot.services.hardware.robots.telecontrol import RobotTelecontrolService


@pytest.mark.asyncio
async def test_set_homing_offsets_raises_on_telemetry_error():
    """If bus.read_telemetry raises, set_homing_offsets should propagate the exception."""
    # Build a minimal test robot (avoid relying on external fixture)
    from datetime import datetime

    from leropilot.models.hardware import (
        DeviceStatus,
        MotorBusDefinition,
        MotorCalibration,
        Robot,
        RobotDefinition,
        RobotMotorBusConnection,
        RobotMotorDefinition,
    )

    motor_def = RobotMotorDefinition(name="joint_1", id=1, brand="dynamixel", model="Test Motor")
    bus_def = MotorBusDefinition(type="dynamixel", motors={"joint_1": motor_def}, baud_rate=1000000)
    definition = RobotDefinition(
        id="test_robot",
        lerobot_name="test_robot",
        display_name="Test Robot",
        description="Test",
        motor_buses={"motor_bus_1": bus_def},
    )

    test_robot = Robot(
        id="test_robot_id",
        name="Test Robot",
        status=DeviceStatus.AVAILABLE,
        definition=definition,
        motor_bus_connections={
            "motor_bus_1": RobotMotorBusConnection(
                motor_bus_type="dynamixel", interface="/dev/ttyUSB0", baudrate=1000000
            )
        },
        calibration_settings={
            "motor_bus_1": [
                MotorCalibration(
                    name="joint_1",
                    id=1,
                    drive_mode=0,
                    homing_offset=0,
                    range_min=-100,
                    range_max=100,
                    soft_homing_offset=False,
                )
            ]
        },
        created_at=datetime.now(),
        is_calibrated=False,
    )

    with (
        patch("leropilot.services.hardware.robots.telecontrol.MotorBus") as mock_bus_class,
        patch("leropilot.services.hardware.robots.telecontrol.CalibrationService"),
    ):
        mock_bus_instance = MagicMock()
        mock_bus_instance.connect = Mock()
        mock_bus_instance.disconnect = Mock()
        mock_bus_instance.motors = {1: MagicMock()}
        mock_bus_instance.scan_motors = Mock(return_value={1: MagicMock()})

        # Make read_telemetry raise
        def bad_read(motor_id):
            raise RuntimeError("telemetry failed")

        mock_bus_instance.read_telemetry = Mock(side_effect=bad_read)
        mock_bus_instance.register_calibration = Mock()
        mock_bus_class.create.return_value = mock_bus_instance

        service = RobotTelecontrolService(test_robot)
        await service.start()
        with pytest.raises(RuntimeError, match="telemetry failed"):
            await service.set_homing_offsets()
        await service.stop()
