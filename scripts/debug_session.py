import asyncio
import json
from unittest.mock import AsyncMock, patch

from leropilot.services.hardware.robots.session import RobotTelecontrolSession


async def main():
    mock_websocket = AsyncMock()
    mock_websocket.receive_text.side_effect = [json.dumps({"type": "heartbeat"}), Exception("WebSocketDisconnect")]
    with (
        patch("leropilot.services.hardware.robots.session.get_robot_manager") as mock_mgr,
        patch("leropilot.services.hardware.robots.session.RobotTelecontrolService") as mock_service_class,
    ):
        from datetime import datetime

        from leropilot.models.hardware import Robot, RobotMotorBusConnection

        test_robot = Robot(
            id="test_robot_id",
            name="Test Robot",
            status="available",
            manufacturer=None,
            labels={},
            created_at=datetime.now(),
            motor_bus_connections={
                "motorbus": RobotMotorBusConnection(
                    motor_bus_type="dynamixel", interface="/dev/ttyUSB0", baudrate=1000000
                )
            },
            is_calibrated=False,
        )
        mock_mgr.return_value.get_robot.return_value = test_robot
        mock_service = AsyncMock()
        mock_service.start = AsyncMock()
        mock_service.stop = AsyncMock()
        mock_service_class.return_value = mock_service

        session = RobotTelecontrolSession("test_robot_id")
        try:
            await session.accept(mock_websocket)
        except Exception as e:
            print("accept raised:", e)

        print("send_text calls:")
        for call in mock_websocket.send_text.call_args_list:
            print(call)


asyncio.run(main())
