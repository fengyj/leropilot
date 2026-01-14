import asyncio
from datetime import datetime

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from leropilot.logger import get_logger
from leropilot.models.hardware import DeviceStatus
from leropilot.services.hardware.motors import MotorService
from leropilot.services.hardware.robots import get_robot_manager
from leropilot.services.pty import get_pty_session

logger = get_logger(__name__)

router = APIRouter(prefix="/api/ws", tags=["WebSockets"])


@router.websocket("/pty_sessions/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str) -> None:
    logger.info(f"WebSocket connection attempt for session {session_id}")

    # Import the sessions dict to check what's available

    pty = get_pty_session(session_id)

    # Security: Validate session existence AND initialization
    if pty is None:
        logger.error(f"Session {session_id} not found in available sessions")
        # Must accept before closing to avoid 500 error
        await websocket.accept()
        await websocket.close(code=4004, reason="Session not found")
        return

    # Defensive check: ensure PTY is fully initialized
    if pty.fd is None and pty.pty is None:
        logger.error(f"Session {session_id} found but not fully initialized")
        # Must accept before closing to avoid 500 error
        await websocket.accept()
        await websocket.close(code=4003, reason="Session not ready")
        return

    logger.info(f"Session {session_id} found and initialized, accepting WebSocket connection")
    await websocket.accept()
    logger.info(f"WebSocket connection accepted for session {session_id}")

    loop = asyncio.get_running_loop()

    # Inject Welcome Message (via Queue)
    pty.write_system_message("Connected to Terminal.", "green")

    # --- Task: PTY -> WebSocket ---
    async def pty_reader() -> None:
        try:
            while True:
                # run_in_executor avoids blocking the Async Event Loop
                # pty.read is now thread-safe reading from internal Queue
                data = await loop.run_in_executor(None, pty.read)

                if data is None:
                    logger.info("PTY reader got EOF marker, breaking")
                    break  # EOF marker received

                if not data:
                    # Empty data due to timeout, continue waiting
                    continue

                # Check if WebSocket is still connected before sending
                try:
                    await websocket.send_text(data.decode("utf-8", errors="replace"))
                except Exception as e:
                    logger.info(f"WebSocket send failed: {e}, stopping reader")
                    # WebSocket is closed, stop reading
                    break
        except Exception as e:
            logger.error(f"Reader error: {e}")
            # Don't try to close WebSocket here - let the main handler handle it

    reader_task = asyncio.create_task(pty_reader())
    logger.info(f"PTY reader task started for session {session_id}")

    # --- Loop: WebSocket -> PTY ---
    try:
        logger.info(f"Starting WebSocket message loop for session {session_id}")
        while True:
            msg = await websocket.receive_json()
            logger.debug(f"Received WebSocket message: {msg}")

            msg_type = msg.get("type")

            if msg_type == "input":
                # Raw input pass-through
                pty.write(msg.get("data", ""))

            elif msg_type == "resize":
                pty.resize(msg.get("rows", 24), msg.get("cols", 80))

            elif msg_type == "command":
                # API driven command execution
                cmd = msg.get("command")
                if cmd:
                    pty.write_command(cmd)

    except WebSocketDisconnect:
        logger.info(f"Client disconnected: {session_id}")
    except Exception as e:
        # Log detailed error information for debugging
        import platform

        error_type = type(e).__name__
        error_msg = str(e)
        logger.error(f"WS Loop error (type={error_type}): {error_msg}")

        # Check if PTY is still alive (Windows-specific check)
        if platform.system() == "Windows" and hasattr(pty, "pty") and pty.pty:
            is_alive = pty.pty.isalive()
            logger.error(f"PTY alive status at error: {is_alive}")
            if not is_alive and hasattr(pty.pty, "get_exitstatus"):
                exit_status = pty.pty.get_exitstatus()
                logger.error(f"PTY exit status: {exit_status}")

        # Re-raise to ensure proper cleanup
        raise
    finally:
        # Cleanup
        logger.info(f"Starting cleanup for session {session_id}")
        reader_task.cancel()
        try:
            await reader_task
        except asyncio.CancelledError:
            pass
        logger.info(f"Session {session_id} cleanup completed")


# Camera WebSocket handler removed — use MJPEG endpoint at `/api/hardware/cameras/{id}/mjpeg`.
# WebSocket remains for robot/device telemetry only.

@router.websocket("/hardware/robots/{device_id}")
async def hardware_websocket(
    websocket: WebSocket,
    device_id: str,
    interface: str = Query(..., description="Communication interface"),
    baud_rate: int = Query(1000000, description="Baud rate"),
) -> None:
    """
    Unified Hardware WebSocket (Spec 4.4.1).
    - Status: Occupied during session.
    - Features: Real-time Telemetry stream, Control commands (future).
    - Heartbeat: Client must send ping every 10s. Server timeouts after 30s.
    """
    manager = get_robot_manager()
    device = manager.get_robot(device_id)

    # 1. Validation
    if not device:
        # Must accept before closing to avoid 500 error
        await websocket.accept()
        await websocket.close(code=4004, reason="Device not found")
        return

    if device.status != DeviceStatus.AVAILABLE:
        # Must accept before closing to avoid 500 error
        await websocket.accept()
        await websocket.close(code=4009, reason="Device occupied")
        return

    # 2. Connection Init
    await websocket.accept()

    # Set status to OCCUPIED
    manager.set_device_status(device_id, DeviceStatus.OCCUPIED)

    # NOTE: We instantiate MotorService here directly (or use singleton/DI if preferred)
    # Using new instance is fine as it's mostly a wrapper around drivers
    motor_service = MotorService()
    driver = None
    telemetry_task = None

    # Session State
    last_activity_time = datetime.now().timestamp()

    try:
        # TelemetrySession and driver will be created below; keep this block for main loop and exception handling

        # Legacy streaming loop removed: telemetry is forwarded from the session queue via `session_forwarder()`.
        # Start TelemetrySession and forward its events to websocket
        from leropilot.services.hardware.telemetry import TelemetrySession

        session = TelemetrySession(device_id=device_id, driver=None, motor_service=motor_service, device=device)
        await session.start()

        # Open driver via session after session is started
        opened = await session.open_driver(
            interface=interface,
            baud_rate=baud_rate,
            brand=device.connection_settings.get("brand", "dynamixel"),
            interface_type=device.connection_settings.get("interface_type", "serial"),
        )
        if not opened:
            await websocket.close(code=4000, reason="Failed to connect driver")
            return

        logger.info(f"WS: Session driver connected for {device_id} on {interface}")

        # Track discovered motor IDs for bulk operations (session exposes target_ids)
        discovered_motor_ids = session.target_ids

        # Check if calibration data exists (required for control commands)
        if not session.calibration_available:
            logger.warning(f"WS: No calibration data for {device_id}, control commands will be blocked")
            # Send info message to client
            await websocket.send_json(
                {
                    "type": "event",
                    "event": {
                        "code": "CALIBRATION_REQUIRED",
                        "severity": "warning",
                        "message": "No calibration data. Control commands are disabled. Telemetry is available.",
                    },
                }
            )

        async def session_forwarder() -> None:
            q = session.subscribe()
            while True:
                try:
                    msg = await q.get()
                    await websocket.send_json(msg)
                except Exception as e:
                    logger.error(f"Session forwarder error: {e}")
                    break

        telemetry_task = asyncio.create_task(session_forwarder())

        # 4. Main Loop (Control & Heartbeat)
        while True:
            try:
                time_since_activity = datetime.now().timestamp() - last_activity_time
                timeout = 30.0 - time_since_activity
                if timeout <= 0:
                    raise asyncio.TimeoutError("Session timeout")

                msg = await asyncio.wait_for(websocket.receive_json(), timeout=timeout)

                last_activity_time = datetime.now().timestamp()

                msg_type = msg.get("type")

                if msg_type == "ping":
                    await websocket.send_json({"type": "pong"})

                elif msg_type == "start_telemetry":
                    interval = msg.get("interval_ms", 100)
                    if interval < 20:
                        interval = 20
                    # Configure session polling interval and enable polling
                    await session.set_poll_interval_ms(interval)
                    await session.enable_polling()
                    logger.info(f"WS: Telemetry started ({interval}ms)")
                    await websocket.send_json(
                        {
                            "type": "ack",
                            "request_type": "start_telemetry",
                            "success": True,
                            "interval_ms": interval,
                        }
                    )

                elif msg_type == "stop_telemetry":
                    await session.disable_polling()
                    logger.info("WS: Telemetry stopped")
                    await websocket.send_json({"type": "ack", "request_type": "stop_telemetry", "success": True})

                # Motor Control Commands
                elif msg_type == "set_position":
                    motor_id = msg.get("motor_id")
                    position = msg.get("position")
                    if motor_id is None or position is None:
                        await websocket.send_json(
                            {
                                "type": "ack",
                                "request_type": "set_position",
                                "success": False,
                                "error": "Missing motor_id or position",
                            }
                        )
                        continue

                    ack = await session.set_position(motor_id, position)
                    await websocket.send_json(
                        {
                            "type": "ack",
                            "request_type": "set_position",
                            "success": ack.get("success", False),
                            "error": ack.get("error"),
                        }
                    )

                elif msg_type == "set_positions":
                    motors = msg.get("motors", [])
                    if not motors:
                        await websocket.send_json(
                            {
                                "type": "ack",
                                "request_type": "set_positions",
                                "success": False,
                                "error": "No motors specified",
                            }
                        )
                        continue

                    ack = await session.set_positions(motors)
                    await websocket.send_json(
                        {
                            "type": "ack",
                            "request_type": "set_positions",
                            "success": ack.get("success", False),
                            "error": ack.get("error"),
                        }
                    )

                elif msg_type == "set_torque":
                    motor_id = msg.get("motor_id")  # None = all motors
                    enabled = msg.get("enabled", False)
                    ack = await session.set_torque(enabled, motor_id)
                    await websocket.send_json(
                        {
                            "type": "ack",
                            "request_type": "set_torque",
                            "success": ack.get("success", False),
                            "error": ack.get("error"),
                        }
                    )

                elif msg_type == "emergency_stop":
                    ack = await session.emergency_stop()
                    # Send immediate ACK to client in addition to the event emitted into the session queue
                    await websocket.send_json(
                        {
                            "type": "ack",
                            "request_type": "emergency_stop",
                            "success": ack.get("success", False),
                            "error": ack.get("error"),
                        }
                    )
                    if ack.get("success"):
                        logger.warning(f"WS: Emergency stop for {device_id}")
                    else:
                        logger.error(f"WS: Emergency stop failed for {device_id}: {ack.get('error')}")

            except asyncio.TimeoutError:
                logger.warning(f"WS: Session timeout for {device_id}")
                await websocket.send_json({"type": "error", "code": "SESSION_TIMEOUT", "message": "No activity"})
                await websocket.close(code=4001, reason="Session timeout")
                break

    except WebSocketDisconnect:
        logger.info(f"WS: Client disconnected {device_id}")
    except Exception as e:
        logger.error(f"WS Error {device_id}: {e}")
        try:
            await websocket.close(code=1011, reason=str(e))
        except Exception:
            pass
    finally:
        # Stop telemetry session (if created) then cancel forwarder
        try:
            # session is created above when telemetry is started
            if 'session' in locals() and session:
                await session.stop()
        except Exception:
            logger.exception(f"Error stopping telemetry session for {device_id}")

        if telemetry_task:
            telemetry_task.cancel()
            try:
                await telemetry_task
            except Exception:
                pass

        # Ensure driver and session are cleanly closed
        try:
            if 'session' in locals() and session:
                await session.disable_polling()
                await session.close_driver()
                await session.stop()
        except Exception:
            logger.exception(f"Error stopping telemetry session for {device_id}")

        manager.set_device_status(device_id, DeviceStatus.AVAILABLE)
