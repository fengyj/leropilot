import fcntl
import logging
import os
import platform
import queue
import re
import signal
import struct
import subprocess
import sys
import termios
import threading
import uuid
from pathlib import Path

# OS Detection
IS_WINDOWS = platform.system() == "Windows"

if IS_WINDOWS:
    from winpty import PtyProcess
else:
    import pty

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
        self.proc: PtyProcess | None = None
        self.pid: int | None = None

        # Handle default path
        user_home = os.path.expanduser("~")
        if not cwd or not os.path.exists(cwd):
            self.cwd = user_home
        else:
            self.cwd = cwd

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
        self._start_pty()
        logger.info(f"PTY session {self.session_id} started, pid: {self.pid}, fd: {self.fd}")

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
            return os.environ.get("COMSPEC", "powershell.exe")
        else:
            return os.environ.get("SHELL", "/bin/bash")

    def _start_pty(self) -> None:
        """Cross-platform PTY start logic"""
        if IS_WINDOWS:
            # Windows: Pywinpty
            try:
                self.proc = PtyProcess.spawn(self.shell_path, dims=(self.rows, self.cols), cwd=self.cwd)
                self.fd = self.proc.fd
                self.pid = self.proc.pid
            except FileNotFoundError:
                # Fallback if shell not found
                self.shell_path = "cmd.exe"
                self.proc = PtyProcess.spawn(self.shell_path, dims=(self.rows, self.cols), cwd=self.cwd)
                self.fd = self.proc.fd
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
        while not self._stop_event.is_set():
            try:
                data = b""
                if IS_WINDOWS:
                    if self.proc is None:
                        break
                    # winpty read may block or return empty
                    data = self.proc.read(1024).encode("utf-8")
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
        if (IS_WINDOWS and self.proc is None) or (not IS_WINDOWS and self.fd is None):
            return

        try:
            if IS_WINDOWS:
                assert self.proc is not None
                self.proc.write(data)
            else:
                assert self.fd is not None
                os.write(self.fd, data.encode("utf-8"))
        except OSError:
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
        if IS_WINDOWS and self.proc:
            self.proc.setwinsize(rows, cols)
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
            if self.proc:
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

                # Fallback to winpty terminate
                try:
                    self.proc.terminate()
                except Exception:
                    pass
                self.proc = None
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
