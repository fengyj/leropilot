import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from leropilot.logger import get_logger
from leropilot.services.pty import get_pty_session

logger = get_logger(__name__)

router = APIRouter(prefix="/api/ws", tags=["terminal-v2"])


@router.websocket("/pty_sessions/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str) -> None:
    logger.info(f"WebSocket connection attempt for session {session_id}")

    # Import the sessions dict to check what's available
    from leropilot.services.pty import sessions

    logger.info(f"Available sessions: {list(sessions.keys())}")

    pty = get_pty_session(session_id)
    logger.info(f"PTY session lookup result: {pty is not None}")
    if pty:
        logger.info(f"PTY session details: id={pty.session_id}, pid={pty.pid}, fd={pty.fd}")

    # Security: Validate session existence
    if pty is None:
        logger.error(f"Session {session_id} not found in available sessions: {list(sessions.keys())}")
        await websocket.close(code=4004, reason="Session not found")
        return

    logger.info(f"Session {session_id} found, accepting WebSocket connection")
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
                    await websocket.send_text(data.decode(errors="ignore"))
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
        logger.error(f"WS Loop error: {e}")
    finally:
        # Cleanup
        logger.info(f"Starting cleanup for session {session_id}")
        reader_task.cancel()
        try:
            await reader_task
        except asyncio.CancelledError:
            pass
        logger.info(f"Session {session_id} cleanup completed")
