import logging
import os
import platform
import queue
import re
import signal
import struct
import subprocess
import sys
import threading
import uuid
from pathlib import Path
from shutil import which

# OS Detection
IS_WINDOWS = platform.system() == "Windows"

if IS_WINDOWS:
    from winpty import PTY
else:
    import fcntl
    import pty
    import termios

logger = logging.getLogger(__name__)

# Global Session Store
# TODO: In production, consider LRU cache or cleanup task for stale sessions
sessions: dict[str, "PtySession"] = {}


class PtySession:
    def __init__(self, cols: int, rows: int, cwd: str | None = None, log_file: str | None = None) -> None:
        self.session_id = str(uuid.uuid4())
        self.cols = cols
        self.rows = rows
        self.fd: int | None = None
        self.pty: PTY | None = None  # Windows: low-level PTY object
        self.pid: int | None = None

        # Handle default path and normalize for Windows
        user_home = os.path.expanduser("~")
        if not cwd or not os.path.exists(cwd):
            self.cwd = user_home
        else:
            self.cwd = cwd

        # Normalize path for Windows (convert to absolute path with backslashes)
        if IS_WINDOWS:
            self.cwd = os.path.abspath(self.cwd)

        # Output queue: stores bytes from Shell and system messages
        # Maxsize provides backpressure
        self._output_queue: queue.Queue[bytes | None] = queue.Queue(maxsize=1024)
        self._stop_event = threading.Event()
        self._initializing = True  # Flag to consume output during initialization

        # --- Log Filtering ---
        self.log_file = log_file
        self.log_handle = None
        self._log_line_buffer = ""  # Buffer for handling progress bars

        if log_file:
            log_path = Path(log_file)
            log_path.parent.mkdir(parents=True, exist_ok=True)
            self.log_handle = open(log_file, "w", encoding="utf-8", buffering=1)

        sessions[self.session_id] = self

        # 1. Detect & Start Shell
        self.shell_path = self._detect_shell()
        logger.info(f"Starting PTY session {self.session_id} with shell: {self.shell_path}")
        print(f"[PTY DEBUG] Starting PTY session {self.session_id} with shell: {self.shell_path}", flush=True)
        self._start_pty()
        logger.info(f"PTY session {self.session_id} started, pid: {self.pid}, fd: {self.fd}")
        print(f"[PTY DEBUG] PTY session started, pid: {self.pid}, fd: {self.fd}", flush=True)

        # 2. Start Background Reader Thread
        self._reader_thread = threading.Thread(target=self._read_loop, daemon=True, name="PtyReader")
        self._reader_thread.start()
        logger.info(f"PTY reader thread started for session {self.session_id}")

        # 3. Inject Shell Integration (OSC 633) in background
        # This will run in a separate thread to avoid blocking __init__
        init_thread = threading.Thread(target=self._complete_initialization, daemon=True, name="PtyInit")
        init_thread.start()

        logger.info(f"PTY session {self.session_id} created, initialization in progress")

    def _detect_shell(self) -> str:
        if IS_WINDOWS:
            # COMSPEC is usually set to cmd.exe on Windows
            # Default to cmd.exe instead of powershell for better compatibility
            return os.environ.get("COMSPEC", "cmd.exe")
        else:
            return os.environ.get("SHELL", "/bin/bash")

    def _start_pty(self) -> None:
        """Cross-platform PTY start logic"""
        if IS_WINDOWS:
            # Windows: Use low-level PTY class for full control
            # This avoids issues with PtyProcess's internal threading
            try:
                # Log environment for debugging
                comspec = os.environ.get("COMSPEC", "NOT_SET")
                logger.info(f"[PTY SPAWN] Starting Windows PTY spawn - COMSPEC={comspec}, shell_path={self.shell_path}")
                print(f"[PTY DEBUG] COMSPEC={comspec}, requested shell={self.shell_path}", flush=True)

                # Find the full path to the shell
                shell_cmd = self.shell_path
                shell_full_path = which(shell_cmd)
                if shell_full_path:
                    logger.info(f"[PTY SPAWN] Resolved shell path: {shell_full_path}")
                    shell_cmd = shell_full_path
                else:
                    logger.warning(f"[PTY SPAWN] Could not find shell in PATH: {shell_cmd}")

                # Verify CWD exists and is accessible
                if not os.path.exists(self.cwd):
                    logger.error(f"[PTY SPAWN] CWD does not exist: {self.cwd}")
                    raise RuntimeError(f"CWD does not exist: {self.cwd}")

                logger.info(f"[PTY SPAWN] CWD exists and is accessible: {self.cwd}")
                print(f"[PTY DEBUG] CWD verified: {self.cwd}", flush=True)

                print(f"[PTY DEBUG] Creating Windows PTY with cols={self.cols}, rows={self.rows}", flush=True)
                logger.info(f"[PTY SPAWN] Creating PTY with dimensions: cols={self.cols}, rows={self.rows}")

                # Create PTY with dimensions (cols, rows)
                self.pty = PTY(self.cols, self.rows)
                logger.info("[PTY SPAWN] PTY object created successfully")

                print(f"[PTY DEBUG] Spawning shell: {shell_cmd}, cwd={self.cwd}", flush=True)
                logger.info(f"[PTY SPAWN] About to spawn: shell={shell_cmd}, cwd={self.cwd}")

                # Spawn the shell process
                # NOTE: cmd.exe runs interactively by default in PTY mode - no /K needed
                # Adding /K as "cmd.exe /K" causes spawn to fail because winpty treats
                # it as a single filename, not as separate arguments
                spawn_result = self.pty.spawn(shell_cmd, cwd=self.cwd)
                logger.info(f"[PTY SPAWN] spawn() returned: {spawn_result}")

                if not spawn_result:
                    raise RuntimeError(f"Failed to spawn shell: {shell_cmd}")

                self.fd = self.pty.fd
                self.pid = self.pty.pid
                print(f"[PTY DEBUG] Windows PTY spawned: pid={self.pid}, fd={self.fd}", flush=True)
                logger.info(f"[PTY SPAWN] Spawn successful - pid={self.pid}, fd={self.fd}")

                # Check if process is alive immediately after spawn
                import time

                # Give cmd.exe more time to initialize
                time.sleep(0.5)
                is_alive = self.pty.isalive()
                print(f"[PTY DEBUG] PTY process alive after 0.5s wait: {is_alive}", flush=True)
                logger.info(f"[PTY SPAWN] Process alive check after 0.5s: {is_alive}")

                if not is_alive:
                    exit_status = self.pty.get_exitstatus()
                    print(
                        f"[PTY DEBUG] PTY died after spawn, exit status: {exit_status} (0x{exit_status:X})", flush=True
                    )
                    logger.error(
                        f"[PTY SPAWN] Process died immediately - exit_status={exit_status} (0x{exit_status:X})"
                    )
                else:
                    logger.info("[PTY SPAWN] Process is alive and ready")

            except Exception as e:
                import traceback

                error_details = traceback.format_exc()
                print(f"[PTY DEBUG] Exception during PTY start: {e}\n{error_details}", flush=True)
                logger.error(f"[PTY SPAWN] Exception during start: {e}\n{error_details}")

                # Fallback to cmd.exe (without /K argument)
                logger.info("[PTY SPAWN] Attempting fallback to cmd.exe")
                self.shell_path = "cmd.exe"
                shell_full_path = which(self.shell_path) or self.shell_path
                self.pty = PTY(self.cols, self.rows)
                if not self.pty.spawn(shell_full_path, cwd=self.cwd):
                    raise RuntimeError(f"Failed to spawn fallback shell: {shell_full_path}") from e
                self.fd = self.pty.fd
                self.pid = self.pty.pid
                logger.info(f"[PTY SPAWN] Fallback spawn successful - pid={self.pid}")
        else:
            # Linux/macOS: Native PTY
            self.pid, self.fd = pty.fork()
            if self.pid == 0:  # Child process
                try:
                    os.chdir(self.cwd)
                except OSError:
                    pass  # Keep current dir if chdir fails
                # Set Standard Terminal Environment
                os.environ["TERM"] = "xterm-256color"
                # Replace current process with shell
                try:
                    os.execv(self.shell_path, [self.shell_path])
                except OSError as e:
                    # If exec fails, must exit child process
                    sys.stderr.write(f"Failed to exec shell: {e}\n")
                    sys.exit(1)
            else:  # Parent process
                self._resize_linux(self.rows, self.cols)

    def _read_loop(self) -> None:
        """Background thread: Physical PTY -> Queue"""
        import time as time_module

        print(f"[PTY DEBUG] _read_loop started for session {self.session_id}", flush=True)
        logger.info(f"[READ_LOOP] Started for session {self.session_id}, IS_WINDOWS={IS_WINDOWS}")
        logger.info(f"[READ_LOOP] self.pty={self.pty}, self.fd={self.fd}, self.pid={self.pid}")

        # On Windows, give the PTY a moment to fully initialize
        if IS_WINDOWS:
            time_module.sleep(0.2)
            if self.pty:
                is_alive = self.pty.isalive()
                print(f"[PTY DEBUG] After startup wait, PTY isalive={is_alive}", flush=True)
                logger.info(f"[READ_LOOP] After startup wait, PTY isalive={is_alive}")
                if not is_alive:
                    print("[PTY DEBUG] PTY process died before read loop could start", flush=True)
                    logger.error("[READ_LOOP] PTY process died before read loop could start")
                    self._output_queue.put(None)
                    return

        read_count = 0
        consecutive_empty = 0
        while not self._stop_event.is_set():
            try:
                data = b""
                if IS_WINDOWS:
                    if self.pty is None:
                        logger.info("[READ_LOOP] PTY is None, breaking read loop")
                        break
                    # Use low-level PTY.read() with blocking=False and polling
                    # This avoids issues with blocking reads on Windows
                    try:
                        read_count += 1
                        if read_count <= 5:
                            logger.info(f"[READ_LOOP] read attempt #{read_count}, isalive={self.pty.isalive()}")

                        # Use non-blocking read
                        text = self.pty.read(blocking=False)
                        if text:
                            data = text.encode("utf-8")
                            consecutive_empty = 0
                            if read_count <= 5:
                                logger.info(f"PTY read #{read_count} got {len(data)} bytes")
                        else:
                            consecutive_empty += 1
                            # Check if process is still alive
                            is_alive = self.pty.isalive()
                            if read_count <= 5 or consecutive_empty <= 3:
                                logger.info(
                                    f"PTY read #{read_count} empty (consecutive={consecutive_empty}), alive={is_alive}"
                                )
                            if not is_alive:
                                # Process exited, but might still have buffered output
                                # Try a few more reads before giving up
                                if consecutive_empty > 5:
                                    logger.info("PTY process not alive and no more data, breaking read loop")
                                    break
                            # Sleep briefly to avoid busy-waiting
                            time_module.sleep(0.05)
                            continue
                    except Exception as e:
                        logger.warning(f"PTY read error: {e}, isalive={self.pty.isalive() if self.pty else 'N/A'}")
                        if "EOF" in str(e) or (self.pty and not self.pty.isalive()):
                            break
                        time_module.sleep(0.05)
                        continue
                else:
                    if self.fd is None:
                        break
                    # Linux read is blocking
                    data = os.read(self.fd, 1024)

                if not data:
                    # EOF detected (Shell exited)
                    break

                # Write to log (filtered)
                if self.log_handle:
                    cleaned = self._clean_for_log(data)
                    if cleaned:
                        self.log_handle.write(cleaned)

                # During initialization, only log output, don't queue it
                if self._initializing:
                    continue

                # After initialization, put data in queue for client consumption
                try:
                    self._output_queue.put(data, block=True, timeout=0.1)
                except queue.Full:
                    # Queue is full, drop oldest data to avoid blocking
                    logger.warning(f"Output queue full for session {self.session_id}, dropping data")
                    try:
                        self._output_queue.get_nowait()
                        self._output_queue.put(data, block=False)
                    except (queue.Empty, queue.Full):
                        pass

            except (OSError, EOFError):
                break
            except Exception as e:
                if not self._stop_event.is_set():
                    logger.error(f"PTY read loop error: {e}")
                break

        # Signal EOF to consumer
        self._output_queue.put(None)

    def _complete_initialization(self) -> None:
        """Complete initialization in background thread."""
        import time

        # Wait a short time for shell to initialize
        time.sleep(0.3)

        # Clear any data that might have been queued
        while not self._output_queue.empty():
            try:
                self._output_queue.get_nowait()
            except queue.Empty:
                break

        # Mark initialization complete - start queuing output for client
        self._initializing = False
        logger.info(f"PTY session {self.session_id} initialization completed, ready for client")

        # Now inject shell integration after client can receive output
        time.sleep(0.1)
        self._inject_integration_script()

    def _inject_integration_script(self) -> None:
        """Load VS Code Shell Integration scripts"""
        # Determine resource path relative to this file
        # src/leropilot/services/pty/session.py -> src/leropilot/resources/shells
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        script_dir = os.path.join(base_dir, "resources", "shells")

        cmd = ""
        shell_name = os.path.basename(self.shell_path).lower()

        if IS_WINDOWS and ("powershell" in shell_name or "pwsh" in shell_name):
            path = os.path.join(script_dir, "shellIntegration.ps1")
            if os.path.exists(path):
                cmd = f". '{path}'"

        elif "zsh" in shell_name:
            path = os.path.join(script_dir, "shellIntegration-rc.zsh")
            if os.path.exists(path):
                cmd = f"source '{path}'"

        elif "bash" in shell_name:
            path = os.path.join(script_dir, "shellIntegration-bash.sh")
            if os.path.exists(path):
                cmd = f"source '{path}'"

        elif "fish" in shell_name:
            path = os.path.join(script_dir, "shellIntegration.fish")
            if os.path.exists(path):
                cmd = f"source '{path}'"

        if cmd:
            # Auto-execute injection command and clear screen
            self.write_command(cmd)
            self.write_command("clear" if not IS_WINDOWS else "Clear-Host")

    # --- Public API ---

    def read(self, timeout: float = 1.0) -> bytes:
        """Consumer method: Read from aggregated queue"""
        try:
            data = self._output_queue.get(timeout=timeout)
            if data is None:
                logger.info(f"PTY session {self.session_id} received EOF marker")
                return b""  # EOF marker
            return data
        except queue.Empty:
            return b""

    def write(self, data: str) -> None:
        if (IS_WINDOWS and self.pty is None) or (not IS_WINDOWS and self.fd is None):
            return

        try:
            if IS_WINDOWS:
                assert self.pty is not None
                self.pty.write(data)
            else:
                assert self.fd is not None
                os.write(self.fd, data.encode("utf-8"))
        except (OSError, EOFError):
            pass

    def write_command(self, command: str) -> None:
        """
        Execute single or multi-line command.
        Strips trailing whitespace but preserves leading indentation.
        """
        if not command:
            return

        # Remove trailing whitespace, keep leading indentation
        cmd = command.rstrip()
        if not cmd:
            return

        # Append \r to trigger execution
        self.write(cmd + "\r")

    def write_system_message(self, message: str, color: str = "green") -> None:
        """Utility: Inject system message directly to output stream"""
        colors = {
            "red": "\x1b[31m",
            "green": "\x1b[32m",
            "yellow": "\x1b[33m",
            "blue": "\x1b[34m",
            "reset": "\x1b[0m",
        }
        c = colors.get(color, colors["reset"])
        formatted = f"\r\n{c}[System]: {message}{colors['reset']}\r\n"
        self._output_queue.put(formatted.encode("utf-8"))

    def resize(self, rows: int, cols: int) -> None:
        self.rows = rows
        self.cols = cols
        if IS_WINDOWS and self.pty:
            # Check if PTY is still alive before attempting resize
            try:
                if not self.pty.isalive():
                    logger.warning(f"Attempted to resize dead PTY session {self.session_id}")
                    return
                self.pty.set_size(cols, rows)
            except Exception as e:
                logger.warning(f"Failed to resize PTY session {self.session_id}: {e}")
        elif not IS_WINDOWS and self.fd:
            self._resize_linux(rows, cols)

    def _resize_linux(self, rows: int, cols: int) -> None:
        if self.fd is None:
            return
        try:
            s = struct.pack("HHHH", rows, cols, 0, 0)
            fcntl.ioctl(self.fd, termios.TIOCSWINSZ, s)
        except OSError:
            pass

    def _clean_for_log(self, data: bytes) -> str:
        """
        Clean ANSI control sequences and handle progress bar overwrites.

        Strategy:
        1. Handle \r (carriage return) - progress bars use \r to overwrite current line
        2. Remove ANSI color and control sequences
        3. Only return complete lines (ending with \n)
        """
        try:
            text = data.decode("utf-8", errors="replace")
        except Exception:
            return ""

        # 1. Handle \r (carriage return) - progress bar overwrite logic
        if "\r" in text:
            # Split by \r
            parts = text.split("\r")

            # All parts except the last are overwritten content
            # We only keep the last non-empty part
            for part in parts[:-1]:
                if part:
                    self._log_line_buffer = part

            # Handle the last part
            last_part = parts[-1]
            if "\n" in last_part:
                # Contains newline, line is complete
                lines = last_part.split("\n")
                # First line is continuation of buffer
                result_lines = []
                if self._log_line_buffer or lines[0]:
                    result_lines.append(self._log_line_buffer + lines[0])
                    self._log_line_buffer = ""
                # Add other complete lines
                result_lines.extend(lines[1:-1])
                # Last part (possibly empty) becomes new buffer
                self._log_line_buffer = lines[-1]

                text = "\n".join(result_lines) + "\n"
            else:
                # No newline, update buffer and wait
                self._log_line_buffer = last_part
                return ""
        else:
            # No \r, normal line handling
            if "\n" in text:
                lines = text.split("\n")
                result_lines = []
                if self._log_line_buffer or lines[0]:
                    result_lines.append(self._log_line_buffer + lines[0])
                    self._log_line_buffer = ""
                result_lines.extend(lines[1:-1])
                self._log_line_buffer = lines[-1]

                text = "\n".join(result_lines) + "\n"
            else:
                # No complete line, accumulate in buffer
                self._log_line_buffer += text
                return ""

        # 2. Remove ANSI control sequences
        # Match ESC [ ... m (colors)
        # Match ESC [ ... (other control sequences)
        ansi_escape = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
        text = ansi_escape.sub("", text)

        return text

    def close(self) -> None:
        logger.info(f"Closing session {self.session_id}")
        self._stop_event.set()

        # Flush remaining log buffer
        if self.log_handle:
            if self._log_line_buffer:
                # Remove ANSI sequences from remaining buffer
                ansi_escape = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
                cleaned = ansi_escape.sub("", self._log_line_buffer)
                self.log_handle.write(cleaned + "\n")
            self.log_handle.close()

        if IS_WINDOWS:
            if self.pty:
                # Use taskkill to kill the entire process tree
                if self.pid:
                    try:
                        subprocess.run(
                            ["taskkill", "/F", "/T", "/PID", str(self.pid)],
                            check=False,
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                        )
                    except Exception as e:
                        logger.warning(f"Failed to taskkill process tree: {e}")

                # Clean up PTY object
                try:
                    del self.pty
                except Exception:
                    pass
                self.pty = None
        else:
            if self.fd:
                try:
                    os.close(self.fd)
                except OSError:
                    pass
                self.fd = None
            if self.pid:
                try:
                    # Kill process group to clean up children
                    os.killpg(self.pid, signal.SIGKILL)
                    os.waitpid(self.pid, 0)
                except OSError:
                    pass
                self.pid = None

        sessions.pop(self.session_id, None)


def get_pty_session(session_id: str) -> PtySession | None:
    return sessions.get(session_id)
