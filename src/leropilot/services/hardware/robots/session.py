"""WebSocket session for robot teleoperation."""

import asyncio
import json
import logging
from datetime import datetime, timezone

from fastapi import WebSocket, WebSocketDisconnect

from leropilot.exceptions import ResourceNotFoundError
from leropilot.models.hardware import (
    CalibrationStateMessage,
    CommandAckMessage,
    ErrorMessage,
    RobotTelemetryFrame,
    SessionInitMessage,
)
from leropilot.services.hardware.robots import get_robot_manager
from leropilot.services.hardware.robots.telecontrol import RobotTelecontrolService

logger = logging.getLogger(__name__)


class RobotTelecontrolSession:
    """WebSocket session for real-time robot teleoperation.

    Manages a WebSocket connection for a robot, handling:
    - Session initialization
    - WebSocket message parsing and dispatching
    - Heartbeat monitoring (auto-stop on timeout)
    - Error handling and cleanup
    """

    # Heartbeat timeout (seconds)
    HEARTBEAT_TIMEOUT = 5.0

    def __init__(self, robot_id: str, normalized: bool = False, fps: int = 30) -> None:
        """Initialize TelecontrolSession.

        Args:
            robot_id: Robot ID to control.
            normalized: If True, telemetry is normalized to [-1, 1].
            fps: Target frames per second for telemetry (default: 30).

        Raises:
            ResourceNotFoundError: If robot not found.
            OperationalError: If robot is not available.
        """
        self._robot_id = robot_id
        self._normalized = normalized
        self._fps = fps
        self._websocket: WebSocket | None = None
        self._service: RobotTelecontrolService | None = None
        self._running = False
        self._last_heartbeat: datetime | None = None
        self._heartbeat_task: asyncio.Task | None = None

        # Validate robot exists
        manager = get_robot_manager()
        robot = manager.get_robot(robot_id)
        if not robot:
            raise ResourceNotFoundError("hardware.robot_device.not_found", id=robot_id)

        # Will be fully initialized in accept()
        self._robot = robot

    async def accept(self, websocket: WebSocket) -> None:
        """Accept and initialize WebSocket connection.

        Initializes the teleoperation service, sends session init message,
        and enters message loop.

        Args:
            websocket: FastAPI WebSocket connection.

        Raises:
            OperationalError: If service initialization fails.
        """
        self._websocket = websocket
        await websocket.accept()
        logger.info(f"WebSocket connection accepted for robot {self._robot_id}")

        try:
            # Create and start teleoperation service
            self._service = RobotTelecontrolService(self._robot, normalized=self._normalized)
            await self._service.start(callback=self._send_telemetry_frame, fps=self._fps)

            # Update last heartbeat
            self._last_heartbeat = datetime.now(timezone.utc)

            # Send session init message
            init_msg = SessionInitMessage(
                robot_id=self._robot_id,
                normalized=self._normalized,
                fps=self._fps,
            )
            await websocket.send_text(init_msg.model_dump_json())

            # Start heartbeat monitor task
            self._heartbeat_task = asyncio.create_task(self._monitor_heartbeat())

            # Enter message loop
            self._running = True
            await self._message_loop()

        except Exception as e:
            # Log full exception and attempt to notify client. If notification succeeds,
            # do not re-raise (client has been informed). If notification fails, re-raise
            # the send exception so upstream callers/tests observe the failure.
            logger.exception(f"Error in WebSocket session for robot {self._robot_id}: {e}")
            error_msg = ErrorMessage(
                code="SESSION_INIT_FAILED",
                message=f"Failed to initialize teleoperation session: {str(e)}",
            )
            try:
                await websocket.send_text(error_msg.model_dump_json())
            except Exception as send_exc:
                logger.exception("Failed to send session init failure message")
                # If we cannot notify the client, propagate the send error
                raise send_exc from e
            # Error was reported to client; do not re-raise the original exception
            return
        finally:
            await self.stop()

    async def _message_loop(self) -> None:
        """Main WebSocket message processing loop.

        Receives JSON commands from client and dispatches to appropriate handler.
        """
        try:
            while self._running and self._websocket is not None:
                # Small sleep to allow mocked AsyncMock side_effect to be scheduled
                await asyncio.sleep(0.001)
                try:
                    data = await self._websocket.receive_text()
                except Exception as e:
                    logger.info(f"receive_text raised: {e}")
                    raise
                logger.info(f"Received raw message for robot {self._robot_id}: {data}")
                try:
                    # Parse command
                    cmd_data = json.loads(data)
                    cmd_type = cmd_data.get("type")

                    # Dispatch to handler
                    if cmd_type == "heartbeat":
                        await self._handle_heartbeat()
                    elif cmd_type == "emergency_stop":
                        await self._handle_emergency_stop()
                    elif cmd_type == "polling":
                        await self._handle_polling(cmd_data)
                    elif cmd_type == "set_positions":
                        await self._handle_set_positions(cmd_data)
                    elif cmd_type == "set_torques":
                        await self._handle_set_torques(cmd_data)
                    elif cmd_type == "set_velocities":
                        await self._handle_set_velocities(cmd_data)
                    elif cmd_type == "set_homing_offsets":
                        await self._handle_set_homing_offsets()
                    elif cmd_type == "set_ranges":
                        await self._handle_set_ranges(cmd_data)
                    elif cmd_type == "calibration_start":
                        await self._handle_calibration_start(cmd_data)
                    elif cmd_type == "calibration_next":
                        await self._handle_calibration_next()
                    elif cmd_type == "calibration_save":
                        await self._handle_calibration_save()
                    else:
                        error_msg = ErrorMessage(
                            code="UNKNOWN_COMMAND",
                            message=f"Unknown command type: {cmd_type}",
                        )
                        await self._websocket.send_text(error_msg.model_dump_json())

                except json.JSONDecodeError as e:
                    logger.exception(f"Failed to parse WebSocket message: {e}")
                    error_msg = ErrorMessage(
                        code="INVALID_JSON",
                        message="Failed to parse JSON command",
                    )
                    try:
                        await self._websocket.send_text(error_msg.model_dump_json())
                    except Exception as send_exc:
                        logger.exception("Failed to send INVALID_JSON message")
                        # Ensure upstream is aware of send failures
                        raise send_exc from e
        except WebSocketDisconnect:
            logger.info(f"WebSocket disconnected for robot {self._robot_id}")
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.exception(f"Error in message loop: {e}")

    async def _monitor_heartbeat(self) -> None:
        """Monitor heartbeat and auto-stop on timeout.

        Checks periodically if heartbeat has been received within the timeout window.
        If not, automatically stops the session.
        """
        try:
            while self._running:
                await asyncio.sleep(1.0)

                if self._last_heartbeat is None:
                    continue

                time_since_heartbeat = (datetime.now(timezone.utc) - self._last_heartbeat).total_seconds()
                if time_since_heartbeat > self.HEARTBEAT_TIMEOUT:
                    logger.warning(
                        f"Heartbeat timeout for robot {self._robot_id} "
                        f"({time_since_heartbeat:.1f}s > {self.HEARTBEAT_TIMEOUT}s)"
                    )
                    await self.stop()
                    break

        except asyncio.CancelledError:
            pass

    async def _handle_heartbeat(self) -> None:
        """Handle heartbeat command."""
        self._last_heartbeat = datetime.now(timezone.utc)
        logger.info(f"Heartbeat received for robot {self._robot_id}")
        # Send ack
        ack = CommandAckMessage(command_type="heartbeat", success=True)
        # Let send_text exceptions propagate so callers/tests can observe them
        await self._websocket.send_text(ack.model_dump_json())

    async def _handle_emergency_stop(self) -> None:
        """Handle emergency stop command."""
        logger.warning(f"Emergency stop requested for robot {self._robot_id}")
        if self._service:
            await self._service.emergency_stop()
        ack = CommandAckMessage(command_type="emergency_stop", success=True)
        await self._websocket.send_text(ack.model_dump_json())

    async def _handle_polling(self, cmd_data: dict) -> None:
        """Handle polling control command."""
        enabled = cmd_data.get("enabled", True)
        if self._service:
            await self._service.polling(enabled)
        ack = CommandAckMessage(
            command_type="polling",
            success=True,
            message=f"Polling {'enabled' if enabled else 'disabled'}",
        )
        await self._websocket.send_text(ack.model_dump_json())

    async def _handle_set_positions(self, cmd_data: dict) -> None:
        """Handle set positions command.

        Expected format: motor_positions = {bus_name: {motor_name: position}}
        """
        positions = cmd_data.get("motor_positions", {})
        clamped_motors: dict[str, list[str]] = {}

        if self._service:
            clamped_motors = await self._service.set_positions(positions)

        # Count total motors affected
        total_motors = sum(len(motors) for motors in positions.values())

        # Build message with clamping info if any motors were clamped
        message = f"Set positions for {total_motors} motor(s)"
        if any(clamped_motors.values()):
            clamped_details = []
            for _bus_name, clamped_list in clamped_motors.items():
                if clamped_list:
                    clamped_details.extend(clamped_list)
            if clamped_details:
                message += f"; clamped: {'; '.join(clamped_details)}"

        ack = CommandAckMessage(
            command_type="set_positions",
            success=True,
            message=message,
        )
        await self._websocket.send_text(ack.model_dump_json())

    async def _handle_set_torques(self, cmd_data: dict) -> None:
        """Handle set torques command.

        Expected format: motor_enabled = {bus_name: {motor_name: enabled}}
        """
        motor_enabled = cmd_data.get("motor_enabled", {})
        if self._service:
            await self._service.set_torques(motor_enabled)
        # Count total motors affected
        total_motors = sum(len(motors) for motors in motor_enabled.values())
        ack = CommandAckMessage(
            command_type="set_torques",
            success=True,
            message=f"Set torques for {total_motors} motor(s)",
        )
        await self._websocket.send_text(ack.model_dump_json())

    async def _handle_set_velocities(self, cmd_data: dict) -> None:
        """Handle set velocities command.

        Expected format: motor_velocities = {bus_name: {motor_name: velocity}}
        """
        velocities = cmd_data.get("motor_velocities", {})
        validated_motors: dict[str, list[str]] = {}

        if self._service:
            validated_motors = await self._service.set_velocities(velocities)

        # Count total motors affected
        total_motors = sum(len(motors) for motors in velocities.values())

        # Build message with validation info if any motors had validation notes
        message = f"Set velocities for {total_motors} motor(s)"
        if any(validated_motors.values()):
            validation_details = []
            for _bus_name, validated_list in validated_motors.items():
                if validated_list:
                    validation_details.extend(validated_list)
            if validation_details:
                message += f"; warnings: {'; '.join(validation_details)}"

        ack = CommandAckMessage(
            command_type="set_velocities",
            success=True,
            message=message,
        )
        await self._websocket.send_text(ack.model_dump_json())

    async def _handle_set_homing_offsets(self) -> None:
        """Handle set homing offsets command.

        New behavior: no payload required; set homing offsets for all motors on all
        configured motor buses.
        """
        total_motors = 0
        if self._service:
            total_motors = await self._service.set_homing_offsets()

        ack = CommandAckMessage(
            command_type="set_homing_offsets",
            success=True,
            message=f"Set homing offsets for {total_motors} motor(s)",
        )
        await self._websocket.send_text(ack.model_dump_json())

    async def _handle_set_ranges(self, cmd_data: dict) -> None:
        """Handle set ranges command.

        Expected format: motor_ranges = {bus_name: {motor_name: {range_min, range_max}}}
        """
        motor_ranges = cmd_data.get("motor_ranges", {})

        if self._service:
            await self._service.set_ranges(motor_ranges)

        # Count total motors affected
        total_motors = sum(len(motors) for motors in motor_ranges.values())
        ack = CommandAckMessage(
            command_type="set_ranges",
            success=True,
            message=f"Set ranges for {total_motors} motor(s)",
        )
        await self._websocket.send_text(ack.model_dump_json())

    async def _send_telemetry_frame(self, frame: RobotTelemetryFrame) -> None:
        """Send telemetry frame to client.

        Args:
            frame: RobotTelemetryFrame to send.
        """
        try:
            if self._websocket:
                from leropilot.models.hardware import TelemetryMessage

                msg = TelemetryMessage(frame=frame)
                await self._websocket.send_text(msg.model_dump_json())
        except Exception as e:
            logger.exception(f"Error sending telemetry frame: {e}")

    async def _handle_calibration_start(self, cmd_data: dict) -> None:
        """Handle calibration_start command.

        Expects ``method_id`` in the command payload specifying which calibration
        method to use (e.g. ``'halfway'``, ``'zero_position'``).

        Sends a :class:`CalibrationStateMessage` with the initial step information
        on success, or an :class:`ErrorMessage` on failure.
        """
        method_id = cmd_data.get("method_id", "")
        lang = cmd_data.get("lang", "en")
        if not method_id:
            error_msg = ErrorMessage(
                code="INVALID_COMMAND",
                message="calibration_start requires 'method_id' field",
            )
            await self._websocket.send_text(error_msg.model_dump_json())
            return

        try:
            if self._service is None:
                raise RuntimeError("Telecontrol service not initialized")
            state = await self._service.calibration_start(method_id, lang=lang)
            msg = CalibrationStateMessage(
                step_index=state.step_index,
                step_count=state.step_count,
                is_complete=state.is_complete,
                method_id=state.method_id,
                step_descriptions=state.step_descriptions,
            )
            await self._websocket.send_text(msg.model_dump_json())
        except Exception as e:
            logger.exception(f"Error in calibration_start for robot {self._robot_id}: {e}")
            error_msg = ErrorMessage(
                code="CALIBRATION_START_FAILED",
                message=str(e),
            )
            await self._websocket.send_text(error_msg.model_dump_json())

    async def _handle_calibration_next(self) -> None:
        """Handle calibration_next command.

        Advances the active calibration session by one step.  Sends a
        :class:`CalibrationStateMessage` with updated progress on success,
        or an :class:`ErrorMessage` on failure.
        """
        try:
            if self._service is None:
                raise RuntimeError("Telecontrol service not initialized")
            state = await self._service.calibration_next()
            msg = CalibrationStateMessage(
                step_index=state.step_index,
                step_count=state.step_count,
                is_complete=state.is_complete,
                method_id=state.method_id,
                step_descriptions=state.step_descriptions,
            )
            await self._websocket.send_text(msg.model_dump_json())
        except Exception as e:
            logger.exception(f"Error in calibration_next for robot {self._robot_id}: {e}")
            error_msg = ErrorMessage(
                code="CALIBRATION_NEXT_FAILED",
                message=str(e),
            )
            await self._websocket.send_text(error_msg.model_dump_json())

    async def _handle_calibration_save(self) -> None:
        """Handle calibration_save command.

        Persists calibration data accumulated during the active session and
        ends the calibration state machine.  Sends a
        :class:`CommandAckMessage` on success or an :class:`ErrorMessage`
        on failure.
        """
        try:
            if self._service is None:
                raise RuntimeError("Telecontrol service not initialized")
            await self._service.calibration_save()
            ack = CommandAckMessage(command_type="calibration_save", success=True)
            await self._websocket.send_text(ack.model_dump_json())
        except Exception as e:
            logger.exception(f"Error in calibration_save for robot {self._robot_id}: {e}")
            error_msg = ErrorMessage(
                code="CALIBRATION_SAVE_FAILED",
                message=str(e),
            )
            await self._websocket.send_text(error_msg.model_dump_json())

    async def stop(self) -> None:
        """Stop the session and clean up resources.

        Stops teleoperation service, cancels heartbeat monitor, and closes WebSocket.
        """
        if not self._running:
            return

        self._running = False
        logger.info(f"Stopping session for robot {self._robot_id}")

        # Cancel heartbeat task
        if self._heartbeat_task and not self._heartbeat_task.done():
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass

        # Stop teleoperation service
        if self._service:
            try:
                await self._service.stop()
            except Exception as e:
                logger.exception(f"Error stopping teleoperation service: {e}")

        # Close WebSocket
        if self._websocket:
            try:
                await self._websocket.close()
            except Exception as e:
                logger.exception(f"Error closing WebSocket: {e}")

        logger.info(f"Session stopped for robot {self._robot_id}")
