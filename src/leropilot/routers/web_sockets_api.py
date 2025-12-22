import asyncio
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from leropilot.logger import get_logger
from leropilot.models.hardware import DeviceStatus
from leropilot.services.hardware.manager import get_hardware_manager
from leropilot.services.hardware.motors import MotorService
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


@router.websocket("/hardware/devices/{device_id}")
async def hardware_websocket(
    websocket: WebSocket,
    device_id: str,
    stream: str | None = Query(None),
    interface: str = Query(..., description="Communication interface"),
    baud_rate: int = Query(1000000, description="Baud rate"),
) -> None:
    """
    Unified Hardware WebSocket (Spec 4.4.1).
    - Status: Occupied during session.
    - Features: Real-time Telemetry stream, Control commands (future).
    - Heartbeat: Client must send ping every 10s. Server timeouts after 30s.
    """
    manager = get_hardware_manager()
    device = manager.get_device(device_id)

    # 1. Validation
    if not device:
        await websocket.close(code=4004, reason="Device not found")
        return

    if device.status != DeviceStatus.AVAILABLE:
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
    streaming_enabled = False
    streaming_interval_ms = 100
    last_activity_time = datetime.now().timestamp()

    try:
        # 3. Open Driver (Stateless connection)
        brand = device.connection_settings.get("brand", "dynamixel")
        interface_type = device.connection_settings.get("interface_type", "serial")

        driver = motor_service.create_driver(
            interface=interface, brand=brand, interface_type=interface_type, baud_rate=baud_rate
        )

        if not driver:
            await websocket.close(code=4000, reason="Failed to connect driver")
            return

        logger.info(f"WS: Driver connected for {device_id} on {interface}")

        # Track discovered motor IDs for bulk operations
        discovered_motor_ids = list(range(1, 7))  # Default, should be from scan

        # Check if calibration data exists (required for control commands)
        calibration_available = False
        if device.config and device.config.motors:
            # Check if at least one motor has calibration data
            for _motor_name, motor_cfg in device.config.motors.items():
                if motor_cfg.calibration and motor_cfg.calibration.homing_offset is not None:
                    calibration_available = True
                    break

        if not calibration_available:
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

        # Async Task for Telemetry Streaming
        async def stream_loop() -> None:
            nonlocal streaming_enabled
            while True:
                if streaming_enabled:
                    try:
                        target_ids = discovered_motor_ids
                        robot_type_id = device.labels.get("leropilot.ai/robot_type_id", "unknown")

                        # Get per-motor protection overrides
                        def get_motor_overrides(joint_name: str) -> dict[str, Any] | None:
                            if device.config and device.config.motors:
                                motor_cfg = device.config.motors.get(joint_name)
                                if motor_cfg and motor_cfg.protection:
                                    return motor_cfg.protection.overrides
                            return None

                        # Blocking Read in async loop:
                        def sync_read(_target_ids: list[int], _robot_type_id: str) -> list[dict]:
                            _data = []
                            for mid in _target_ids:
                                # Use motor ID as joint name fallback
                                joint_name = f"motor_{mid}"
                                overrides = get_motor_overrides(joint_name)
                                t = motor_service.read_telemetry_with_protection(
                                    driver, mid, brand, _robot_type_id, overrides
                                )
                                if t:
                                    _data.append(t.model_dump())
                            return _data

                        data = sync_read(target_ids, robot_type_id)

                        msg = {"type": "telemetry", "timestamp": datetime.now().isoformat(), "motors": data}
                        await websocket.send_json(msg)

                    except Exception as e:
                        logger.error(f"WS Telemetry Error: {e}")

                await asyncio.sleep(streaming_interval_ms / 1000.0)

        # Start stream loop
        telemetry_task = asyncio.create_task(stream_loop())

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
                    streaming_interval_ms = interval
                    streaming_enabled = True
                    logger.info(f"WS: Telemetry started ({interval}ms)")

                elif msg_type == "stop_telemetry":
                    streaming_enabled = False
                    logger.info("WS: Telemetry stopped")

                # Motor Control Commands
                elif msg_type == "set_position":
                    # Require calibration for control commands
                    if not calibration_available:
                        await websocket.send_json(
                            {
                                "type": "ack",
                                "request_type": "set_position",
                                "success": False,
                                "error": "Calibration required. Please calibrate the robot first.",
                            }
                        )
                        continue

                    motor_id = msg.get("motor_id")
                    position = msg.get("position")
                    # speed = msg.get("speed")  # Optional
                    try:
                        if driver and motor_id is not None and position is not None:
                            driver.write_goal_position(motor_id, int(position))
                            await websocket.send_json(
                                {"type": "ack", "request_type": "set_position", "success": True, "error": None}
                            )
                        else:
                            await websocket.send_json(
                                {
                                    "type": "ack",
                                    "request_type": "set_position",
                                    "success": False,
                                    "error": "Missing motor_id or position",
                                }
                            )
                    except Exception as e:
                        await websocket.send_json(
                            {"type": "ack", "request_type": "set_position", "success": False, "error": str(e)}
                        )

                elif msg_type == "set_positions":
                    # Require calibration for control commands
                    if not calibration_available:
                        await websocket.send_json(
                            {
                                "type": "ack",
                                "request_type": "set_positions",
                                "success": False,
                                "error": "Calibration required. Please calibrate the robot first.",
                            }
                        )
                        continue

                    motors = msg.get("motors", [])
                    try:
                        if driver and motors:
                            for m in motors:
                                mid = m.get("id")
                                pos = m.get("position")
                                if mid is not None and pos is not None:
                                    driver.write_goal_position(mid, int(pos))
                            await websocket.send_json(
                                {"type": "ack", "request_type": "set_positions", "success": True, "error": None}
                            )
                        else:
                            await websocket.send_json(
                                {
                                    "type": "ack",
                                    "request_type": "set_positions",
                                    "success": False,
                                    "error": "No motors specified",
                                }
                            )
                    except Exception as e:
                        await websocket.send_json(
                            {"type": "ack", "request_type": "set_positions", "success": False, "error": str(e)}
                        )

                elif msg_type == "set_torque":
                    # Require calibration for control commands
                    if not calibration_available:
                        await websocket.send_json(
                            {
                                "type": "ack",
                                "request_type": "set_torque",
                                "success": False,
                                "error": "Calibration required. Please calibrate the robot first.",
                            }
                        )
                        continue

                    motor_id = msg.get("motor_id")  # None = all motors
                    enabled = msg.get("enabled", False)
                    try:
                        if driver:
                            if motor_id is not None:
                                driver.write_torque_enable(motor_id, enabled)
                            else:
                                for mid in discovered_motor_ids:
                                    driver.write_torque_enable(mid, enabled)
                            await websocket.send_json(
                                {"type": "ack", "request_type": "set_torque", "success": True, "error": None}
                            )
                    except Exception as e:
                        await websocket.send_json(
                            {"type": "ack", "request_type": "set_torque", "success": False, "error": str(e)}
                        )

                elif msg_type == "emergency_stop":
                    try:
                        if driver:
                            for mid in discovered_motor_ids:
                                try:
                                    driver.write_torque_enable(mid, False)
                                except Exception:
                                    pass  # Best effort
                            await websocket.send_json(
                                {
                                    "type": "event",
                                    "event": {
                                        "code": "EMERGENCY_STOP",
                                        "severity": "warning",
                                        "message": "Emergency stop triggered - all motors disabled",
                                        "timestamp": datetime.now().isoformat(),
                                    },
                                }
                            )
                            logger.warning(f"WS: Emergency stop for {device_id}")
                    except Exception as e:
                        logger.error(f"WS: Emergency stop error: {e}")

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
        if telemetry_task:
            telemetry_task.cancel()
            try:
                await telemetry_task
            except Exception:
                pass

        if driver:
            try:
                driver.disconnect()
                logger.info(f"WS: Driver disconnected {device_id}")
            except Exception:
                pass

        manager.set_device_status(device_id, DeviceStatus.AVAILABLE)
