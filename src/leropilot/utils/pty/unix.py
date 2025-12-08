"""
Unix PTY Manager using native pty, fcntl, and termios modules.

Platform Support: Linux, macOS, and other Unix-like systems.
"""

import asyncio
import errno
import fcntl
import os
import pty
import struct
import termios
from collections.abc import Callable
from typing import Any

from leropilot.logger import get_logger

logger = get_logger(__name__)


class PTYManagerUnix:
    """
    Manages pseudo-terminal (PTY) for executing commands on Unix systems.

    Platform Support:
        - Linux: ✅ Full support
        - macOS: ✅ Full support
        - Windows: ❌ Use windows.py instead
    """

    def __init__(self) -> None:
        self.fd: int | None = None
        self.pid: int | None = None
        self.exit_code: int | None = None

    def spawn(
        self, argv: list[str], env: dict[str, str] | None = None, cwd: str | None = None, venv_path: str | None = None
    ) -> None:
        """Spawn a process in a pseudo-terminal.

        Args:
            argv: Command to execute
            env: Environment variables to set
            cwd: Working directory
            venv_path: Path to Python virtual environment (will be activated before running command)
        """
        if self.fd is not None:
            raise RuntimeError("PTY already spawned")

        # Create a new PTY
        self.pid, self.fd = pty.fork()

        if self.pid == 0:  # Child process
            # Set environment variables
            if env:
                os.environ.update(env)

            # Change directory if specified
            if cwd:
                try:
                    os.chdir(cwd)
                except OSError as e:
                    print(f"Failed to change directory to {cwd}: {e}")

            # If virtual environment path is provided, activate it
            if venv_path:
                try:
                    venv_bin = os.path.join(venv_path, "bin")
                    if not os.path.exists(venv_bin):
                        print(f"Warning: Virtual environment bin directory not found at {venv_bin}")
                    else:
                        # Add venv bin to PATH so that the command runs with venv activated
                        path = os.environ.get("PATH", "")
                        os.environ["PATH"] = f"{venv_bin}:{path}"

                        # Also set VIRTUAL_ENV for tools that check it
                        os.environ["VIRTUAL_ENV"] = venv_path
                except Exception as e:
                    print(f"Warning: Failed to setup virtual environment: {e}")

            # Execute the command
            try:
                os.execvp(argv[0], argv)
            except OSError as e:
                print(f"Failed to execute command {argv}: {e}")
                os._exit(1)

        # Parent process
        logger.info(f"Spawned process {self.pid} with PTY fd {self.fd}")

    def resize(self, rows: int, cols: int) -> None:
        """Resize the PTY window."""
        if self.fd is None:
            return

        try:
            # struct winsize { unsigned short ws_row; unsigned short ws_col; ... }
            winsize = struct.pack("HHHH", rows, cols, 0, 0)
            fcntl.ioctl(self.fd, termios.TIOCSWINSZ, winsize)
        except OSError as e:
            logger.warning(f"Failed to resize PTY: {e}")

    def write(self, data: bytes) -> None:
        """Write data to the PTY."""
        if self.fd is None:
            return

        try:
            os.write(self.fd, data)
        except OSError as e:
            logger.warning(f"Failed to write to PTY: {e}")

    async def read_loop(self, callback: Callable[[bytes], Any]) -> None:
        """Read from PTY and call callback with data."""
        if self.fd is None:
            return

        loop = asyncio.get_running_loop()
        fd: int = self.fd

        # We use a future to signal when the process exits
        exit_future = loop.create_future()

        # Track pending callback tasks
        pending_tasks = set()

        def _read() -> None:
            try:
                data = os.read(fd, 1024)
                if not data:
                    # EOF
                    if not exit_future.done():
                        exit_future.set_result(None)
                    return

                # Call callback (can be async or sync)
                if asyncio.iscoroutinefunction(callback):
                    task = asyncio.create_task(callback(data))
                    pending_tasks.add(task)
                    task.add_done_callback(pending_tasks.discard)
                else:
                    callback(data)
            except OSError as e:
                if e.errno == errno.EIO:
                    # Input/output error usually means the child process closed the PTY
                    if not exit_future.done():
                        exit_future.set_result(None)
                else:
                    logger.error(f"Error reading from PTY: {e}")
                    if not exit_future.done():
                        exit_future.set_result(None)

        # Register the file descriptor with the event loop
        loop.add_reader(self.fd, _read)

        try:
            await exit_future
            # Wait for all pending tasks to complete
            if pending_tasks:
                await asyncio.gather(*pending_tasks, return_exceptions=True)
        finally:
            if self.fd is not None:
                loop.remove_reader(self.fd)
                self.close()

    def get_exit_code(self) -> int:
        """Get the exit code of the process.

        Returns:
            Exit code (0 for success, non-zero for failure)
        """
        if self.exit_code is not None:
            return self.exit_code
        return 1  # Default to error if not set

    def close(self) -> None:
        """Terminate the process and close the PTY."""
        if self.pid is not None:
            try:
                # Wait for the process to exit and get exit code
                _, status = os.waitpid(self.pid, 0)
                self.exit_code = os.WEXITSTATUS(status) if os.WIFEXITED(status) else 1
                logger.info(f"Process {self.pid} exited with code {self.exit_code}")
            except OSError as e:
                logger.warning(f"Failed to wait for process: {e}")
                self.exit_code = 1
            self.pid = None

        if self.fd is not None:
            try:
                os.close(self.fd)
            except OSError:
                pass
            self.fd = None

        logger.info("PTY closed")
