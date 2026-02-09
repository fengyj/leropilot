"""Unit tests for RobotTelecontrolSession."""

import json
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import WebSocket

from leropilot.exceptions import ResourceNotFoundError
from leropilot.models.hardware import (
    DeviceStatus,
    MotorBusDefinition,
    MotorCalibration,
    Robot,
    RobotDefinition,
    RobotMotorBusConnection,
    RobotMotorDefinition,
)
from leropilot.services.hardware.robots.session import RobotTelecontrolSession

# ============================================================================
# Fixtures
# ============================================================================


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
        description="Test robot",
        motor_buses={"motor_bus_1": motor_bus_def},
    )


@pytest.fixture
def test_robot(mock_robot_definition):
    """Create a test robot."""
    return Robot(
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
            ],
        },
        is_calibrated=False,
    )


@pytest.fixture
def mock_websocket():
    """Create a mock WebSocket."""
    ws = AsyncMock(spec=WebSocket)
    ws.accept = AsyncMock()
    ws.send_text = AsyncMock()
    ws.receive_text = AsyncMock()
    ws.close = AsyncMock()
    return ws


# ============================================================================
# Tests: Session Initialization
# ============================================================================


def test_init_robot_not_found():
    """Test that init raises ResourceNotFoundError when robot not found."""
    with patch("leropilot.services.hardware.robots.session.get_robot_manager") as mock_mgr:
        mock_mgr.return_value.get_robot.return_value = None
        with pytest.raises(ResourceNotFoundError):
            RobotTelecontrolSession("nonexistent_robot_id")


def test_init_robot_found(test_robot):
    """Test that init succeeds when robot exists."""
    with patch("leropilot.services.hardware.robots.session.get_robot_manager") as mock_mgr:
        mock_mgr.return_value.get_robot.return_value = test_robot
        session = RobotTelecontrolSession("test_robot_id", normalized=True)
        assert session._robot_id == "test_robot_id"
        assert session._normalized is True


# ============================================================================
# Tests: WebSocket Accept and Initialization
# ============================================================================


@pytest.mark.asyncio
async def test_accept_initializes_service(test_robot, mock_websocket):
    """Test that accept() initializes the service and sends init message."""
    with (
        patch("leropilot.services.hardware.robots.session.get_robot_manager") as mock_mgr,
        patch("leropilot.services.hardware.robots.session.RobotTelecontrolService") as mock_service_class,
    ):
        mock_mgr.return_value.get_robot.return_value = test_robot
        mock_service = AsyncMock()
        mock_service.start = AsyncMock()
        mock_service.stop = AsyncMock()
        mock_service_class.return_value = mock_service

        # Mock receive_text to raise disconnect after initial message
        mock_websocket.receive_text.side_effect = Exception("WebSocketDisconnect")

        session = RobotTelecontrolSession("test_robot_id", normalized=False)

        try:
            await session.accept(mock_websocket)
        except Exception:
            pass

        # Verify service was created and started
        mock_service_class.assert_called_once()
        mock_service.start.assert_called_once()

        # Verify init message was sent
        mock_websocket.send_text.assert_called()
        sent_msg = mock_websocket.send_text.call_args[0][0]
        msg_data = json.loads(sent_msg)
        assert msg_data["type"] == "session_init"
        assert msg_data["robot_id"] == "test_robot_id"
        assert msg_data["normalized"] is False


# ============================================================================
# Tests: Message Handling
# ============================================================================


@pytest.mark.asyncio
async def test_handle_heartbeat(test_robot, mock_websocket):
    """Test heartbeat command handling."""
    with (
        patch("leropilot.services.hardware.robots.session.get_robot_manager") as mock_mgr,
        patch("leropilot.services.hardware.robots.session.RobotTelecontrolService") as mock_service_class,
    ):
        mock_mgr.return_value.get_robot.return_value = test_robot
        mock_service = AsyncMock()
        mock_service.start = AsyncMock()
        mock_service.stop = AsyncMock()
        mock_service_class.return_value = mock_service

        # Simulate heartbeat message followed by disconnect
        heartbeat_msg = json.dumps({"type": "heartbeat"})
        mock_websocket.receive_text.side_effect = [
            heartbeat_msg,
            Exception("WebSocketDisconnect"),
        ]

        session = RobotTelecontrolSession("test_robot_id")

        try:
            await session.accept(mock_websocket)
        except Exception:
            pass

        # Verify ack was sent
        ack_sent = False
        for call in mock_websocket.send_text.call_args_list:
            msg = call[0][0]
            msg_data = json.loads(msg)
            if msg_data.get("type") == "command_ack":
                assert msg_data["command_type"] == "heartbeat"
                ack_sent = True
        assert ack_sent


@pytest.mark.asyncio
async def test_handle_emergency_stop(test_robot, mock_websocket):
    """Test emergency stop command handling."""
    with (
        patch("leropilot.services.hardware.robots.session.get_robot_manager") as mock_mgr,
        patch("leropilot.services.hardware.robots.session.RobotTelecontrolService") as mock_service_class,
    ):
        mock_mgr.return_value.get_robot.return_value = test_robot
        mock_service = AsyncMock()
        mock_service.start = AsyncMock()
        mock_service.stop = AsyncMock()
        mock_service.emergency_stop = AsyncMock()
        mock_service_class.return_value = mock_service

        stop_msg = json.dumps({"type": "emergency_stop"})
        mock_websocket.receive_text.side_effect = [
            stop_msg,
            Exception("WebSocketDisconnect"),
        ]

        session = RobotTelecontrolSession("test_robot_id")

        try:
            await session.accept(mock_websocket)
        except Exception:
            pass

        # Verify emergency_stop was called
        mock_service.emergency_stop.assert_called()


@pytest.mark.asyncio
async def test_handle_set_positions(test_robot, mock_websocket):
    """Test set positions command handling."""
    with (
        patch("leropilot.services.hardware.robots.session.get_robot_manager") as mock_mgr,
        patch("leropilot.services.hardware.robots.session.RobotTelecontrolService") as mock_service_class,
    ):
        mock_mgr.return_value.get_robot.return_value = test_robot
        mock_service = AsyncMock()
        mock_service.start = AsyncMock()
        mock_service.stop = AsyncMock()
        mock_service.set_positions = AsyncMock()
        mock_service_class.return_value = mock_service

        set_pos_msg = json.dumps(
            {
                "type": "set_positions",
                "motor_positions": {1: 0.5},
            }
        )
        mock_websocket.receive_text.side_effect = [
            set_pos_msg,
            Exception("WebSocketDisconnect"),
        ]

        session = RobotTelecontrolSession("test_robot_id")

        try:
            await session.accept(mock_websocket)
        except Exception:
            pass

        # Verify set_positions was called
        mock_service.set_positions.assert_called()


@pytest.mark.asyncio
async def test_handle_set_torques(test_robot, mock_websocket):
    """Test set torques command handling."""
    with (
        patch("leropilot.services.hardware.robots.session.get_robot_manager") as mock_mgr,
        patch("leropilot.services.hardware.robots.session.RobotTelecontrolService") as mock_service_class,
    ):
        mock_mgr.return_value.get_robot.return_value = test_robot
        mock_service = AsyncMock()
        mock_service.start = AsyncMock()
        mock_service.stop = AsyncMock()
        mock_service.set_torques = AsyncMock()
        mock_service_class.return_value = mock_service

        set_torque_msg = json.dumps(
            {
                "type": "set_torques",
                "motor_enabled": {1: True},
            }
        )
        mock_websocket.receive_text.side_effect = [
            set_torque_msg,
            Exception("WebSocketDisconnect"),
        ]

        session = RobotTelecontrolSession("test_robot_id")

        try:
            await session.accept(mock_websocket)
        except Exception:
            pass

        mock_service.set_torques.assert_called()


@pytest.mark.asyncio
async def test_handle_polling(test_robot, mock_websocket):
    """Test polling control command handling."""
    with (
        patch("leropilot.services.hardware.robots.session.get_robot_manager") as mock_mgr,
        patch("leropilot.services.hardware.robots.session.RobotTelecontrolService") as mock_service_class,
    ):
        mock_mgr.return_value.get_robot.return_value = test_robot
        mock_service = AsyncMock()
        mock_service.start = AsyncMock()
        mock_service.stop = AsyncMock()
        mock_service.polling = AsyncMock()
        mock_service_class.return_value = mock_service

        polling_msg = json.dumps(
            {
                "type": "polling",
                "enabled": False,
            }
        )
        mock_websocket.receive_text.side_effect = [
            polling_msg,
            Exception("WebSocketDisconnect"),
        ]

        session = RobotTelecontrolSession("test_robot_id")

        try:
            await session.accept(mock_websocket)
        except Exception:
            pass

        mock_service.polling.assert_called_with(False)


# ============================================================================
# Tests: Session Cleanup
# ============================================================================


@pytest.mark.asyncio
async def test_stop_cleanup(test_robot):
    """Test that stop() properly cleans up resources."""
    with (
        patch("leropilot.services.hardware.robots.session.get_robot_manager") as mock_mgr,
        patch("leropilot.services.hardware.robots.session.RobotTelecontrolService") as mock_service_class,
    ):
        mock_mgr.return_value.get_robot.return_value = test_robot
        mock_service = AsyncMock()
        mock_service.start = AsyncMock()
        mock_service.stop = AsyncMock()
        mock_service_class.return_value = mock_service

        mock_ws = AsyncMock()
        session = RobotTelecontrolSession("test_robot_id")
        session._websocket = mock_ws
        session._service = mock_service
        session._running = True

        await session.stop()

        assert not session._running
        mock_service.stop.assert_called()
        mock_ws.close.assert_called()


# ============================================================================
# Tests: Error Handling
# ============================================================================


@pytest.mark.asyncio
async def test_invalid_json_handling(test_robot, mock_websocket):
    """Test that invalid JSON is handled gracefully."""
    with (
        patch("leropilot.services.hardware.robots.session.get_robot_manager") as mock_mgr,
        patch("leropilot.services.hardware.robots.session.RobotTelecontrolService") as mock_service_class,
    ):
        mock_mgr.return_value.get_robot.return_value = test_robot
        mock_service = AsyncMock()
        mock_service.start = AsyncMock()
        mock_service.stop = AsyncMock()
        mock_service_class.return_value = mock_service

        # Send invalid JSON
        mock_websocket.receive_text.side_effect = [
            "invalid json {",
            Exception("WebSocketDisconnect"),
        ]

        session = RobotTelecontrolSession("test_robot_id")

        try:
            await session.accept(mock_websocket)
        except Exception:
            pass

        # Verify error message was sent
        error_sent = False
        for call in mock_websocket.send_text.call_args_list:
            msg = call[0][0]
            msg_data = json.loads(msg)
            if msg_data.get("type") == "error":
                assert msg_data["code"] == "INVALID_JSON"
                error_sent = True
        assert error_sent


@pytest.mark.asyncio
async def test_unknown_command_handling(test_robot, mock_websocket):
    """Test that unknown commands are handled gracefully."""
    with (
        patch("leropilot.services.hardware.robots.session.get_robot_manager") as mock_mgr,
        patch("leropilot.services.hardware.robots.session.RobotTelecontrolService") as mock_service_class,
    ):
        mock_mgr.return_value.get_robot.return_value = test_robot
        mock_service = AsyncMock()
        mock_service.start = AsyncMock()
        mock_service.stop = AsyncMock()
        mock_service_class.return_value = mock_service

        # Send unknown command
        mock_websocket.receive_text.side_effect = [
            json.dumps({"type": "unknown_command"}),
            Exception("WebSocketDisconnect"),
        ]

        session = RobotTelecontrolSession("test_robot_id")

        try:
            await session.accept(mock_websocket)
        except Exception:
            pass

        # Verify error message was sent
        error_sent = False
        for call in mock_websocket.send_text.call_args_list:
            msg = call[0][0]
            msg_data = json.loads(msg)
            if msg_data.get("type") == "error":
                assert msg_data["code"] == "UNKNOWN_COMMAND"
                error_sent = True
        assert error_sent
