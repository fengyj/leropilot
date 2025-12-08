"""
Windows PTY Manager implementation using pywinpty.

This provides Windows support for pseudo-terminal operations using ConPTY via pywinpty.
"""

import asyncio
import os
from collections.abc import Callable
from typing import Any

from leropilot.logger import get_logger

logger = get_logger(__name__)

# Windows-specific imports
try:
    from winpty import PtyProcess
except ImportError:
    raise ImportError("pywinpty is required for Windows support. Install it with: pip install pywinpty") from None


class PTYManagerWindows:
    """
    Windows implementation of PTY manager using pywinpty.

    Uses Windows ConPTY (Console Pseudo-Terminal) via the pywinpty library
    to provide PTY-like functionality on Windows.
    """

    def __init__(self) -> None:
        self.process: PtyProcess | None = None
        self._read_task: asyncio.Task[None] | None = None
        self._closed = False

    def spawn(
        self,
        argv: list[str],
        env: dict[str, str] | None = None,
        cwd: str | None = None,
        venv_path: str | None = None,
    ) -> None:
        """
        Spawn a process in a pseudo-terminal.

        Args:
            argv: Command to execute (command and arguments)
            env: Environment variables to set
            cwd: Working directory
            venv_path: Path to Python virtual environment (will be activated)
        """
        if self.process is not None:
            raise RuntimeError("PTY already spawned")

        # Prepare environment
        exec_env = os.environ.copy()
        if env:
            exec_env.update(env)

        # Activate virtual environment if provided
        if venv_path:
            venv_scripts = os.path.join(venv_path, "Scripts")  # Windows uses Scripts, not bin
            if os.path.exists(venv_scripts):
                # Prepend venv Scripts to PATH
                path = exec_env.get("PATH", "")
                exec_env["PATH"] = f"{venv_scripts};{path}"  # Windows uses ; separator
                exec_env["VIRTUAL_ENV"] = venv_path
                logger.info(f"Virtual environment activated: {venv_path}")
            else:
                logger.warning(f"Virtual environment Scripts directory not found at {venv_scripts}")

        # Build command string
        # On Windows, we need to handle command quoting properly
        cmd = " ".join(self._quote_arg(arg) for arg in argv)

        # Working directory
        working_dir = cwd or os.getcwd()

        try:
            # Spawn the process using pywinpty
            self.process = PtyProcess.spawn(
                cmd,
                cwd=working_dir,
                env=exec_env,
                dimensions=(24, 80),  # Default terminal size
            )
            logger.info(f"Spawned Windows PTY process: {cmd}")
        except Exception as e:
            logger.error(f"Failed to spawn Windows PTY process: {e}")
            raise

    def _quote_arg(self, arg: str) -> str:
        """
        Quote argument for Windows command line if needed.

        Args:
            arg: Argument to quote

        Returns:
            Quoted argument if necessary
        """
        # If argument contains spaces or special chars, quote it
        if " " in arg or '"' in arg or "'" in arg:
            # Escape double quotes and wrap in quotes
            return f'"{arg.replace(chr(34), chr(92) + chr(34))}"'
        return arg

    def resize(self, rows: int, cols: int) -> None:
        """
        Resize the PTY window.

        Args:
            rows: Number of rows
            cols: Number of columns
        """
        if self.process is None:
            return

        try:
            self.process.setwinsize(rows, cols)
        except Exception as e:
            logger.warning(f"Failed to resize Windows PTY: {e}")

    def write(self, data: bytes) -> None:
        """
        Write data to the PTY.

        Args:
            data: Bytes to write
        """
        if self.process is None or self._closed:
            return

        try:
            # pywinpty expects string, decode if bytes
            if isinstance(data, bytes):
                data_str = data.decode("utf-8", errors="replace")
            else:
                data_str = data

            self.process.write(data_str)
        except Exception as e:
            logger.warning(f"Failed to write to Windows PTY: {e}")

    async def read_loop(self, callback: Callable[[bytes], Any]) -> None:
        """
        Read from PTY and call callback with data.

        Args:
            callback: Function to call with each chunk of data
        """
        if self.process is None:
            return

        loop = asyncio.get_running_loop()

        try:
            while not self._closed:
                # Read from process in executor to avoid blocking
                try:
                    data = await loop.run_in_executor(
                        None,
                        self._read_chunk,
                    )

                    if data:
                        # Convert to bytes if needed
                        if isinstance(data, str):
                            data_bytes = data.encode("utf-8")
                        else:
                            data_bytes = data

                        # Call callback
                        if asyncio.iscoroutinefunction(callback):
                            await callback(data_bytes)
                        else:
                            callback(data_bytes)
                    else:
                        # No data means process ended
                        break

                    # Small delay to avoid busy loop
                    await asyncio.sleep(0.01)

                except Exception as e:
                    logger.error(f"Error reading from Windows PTY: {e}")
                    break
        finally:
            self.close()

    def _read_chunk(self) -> str | None:
        """
        Read a chunk of data from the process (blocking).

        Returns:
            Data read or None if process ended
        """
        if self.process is None or self._closed:
            return None

        try:
            # Check if process is alive
            if not self.process.isalive():
                return None

            # Read available data
            data = self.process.read(1024)
            return data if data else None

        except Exception:
            return None

    def close(self) -> None:
        """Terminate the process and close the PTY."""
        if self._closed:
            return

        self._closed = True

        if self.process is not None:
            try:
                if self.process.isalive():
                    self.process.terminate(force=True)
                self.process = None
            except Exception as e:
                logger.warning(f"Error closing Windows PTY: {e}")

        logger.info("Windows PTY closed")
