"""Subprocess execution utilities with automatic logging."""

import asyncio
import subprocess
from collections import deque
from collections.abc import AsyncIterator, Callable
from pathlib import Path
from typing import Any

from leropilot.logger import get_logger

logger = get_logger(__name__)


def is_progress_line(line: str) -> bool:
    """
    Check if a line appears to be a progress update (e.g., contains control characters
    like \r, \b, or ANSI escape sequences).
    """
    return "\r" in line or "\b" in line or "\033[" in line


class SubprocessExecutor:
    """Executes subprocess commands with automatic debug logging."""

    @staticmethod
    async def run(
        *args: str,
        cwd: Path | str | None = None,
        env: dict[str, str] | None = None,
        check: bool = False,
        timeout: float | None = None,
    ) -> subprocess.CompletedProcess[bytes]:
        """
        Execute a subprocess command with automatic debug logging.

        Args:
            *args: Command arguments
            cwd: Working directory
            env: Environment variables
            check: Whether to raise exception on non-zero exit code
            timeout: Timeout in seconds
            **kwargs: Additional arguments passed to create_subprocess_exec

        Returns:
            CompletedProcess-like object with returncode, stdout, stderr

        Raises:
            subprocess.CalledProcessError: If check=True and returncode != 0
            asyncio.TimeoutError: If timeout is exceeded
        """
        cmd_str = " ".join(args)
        logger.debug(f"Executing subprocess: {cmd_str}")
        if cwd:
            logger.debug(f"Working directory: {cwd}")

        # Set up pipes constants for stdout and stderr
        stdout_pipe = asyncio.subprocess.PIPE
        stderr_pipe = asyncio.subprocess.PIPE
        cwd_arg = str(cwd) if cwd else None

        try:
            process = await asyncio.create_subprocess_exec(
                *args,
                stdout=stdout_pipe,
                stderr=stderr_pipe,
                cwd=cwd_arg,
                env=env,
            )

            if timeout:
                stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
            else:
                stdout, stderr = await process.communicate()

            # Log outputs at debug level
            if stdout:
                stdout_str = stdout.decode("utf-8", errors="replace")
                logger.debug(f"Subprocess stdout: {stdout_str}")
            if stderr:
                stderr_str = stderr.decode("utf-8", errors="replace")
                logger.debug(f"Subprocess stderr: {stderr_str}")

            # Create a CompletedProcess object
            assert process.returncode is not None
            result = subprocess.CompletedProcess(args, process.returncode, stdout, stderr)

            if check and process.returncode != 0:
                raise subprocess.CalledProcessError(
                    process.returncode,
                    args,
                    stdout.decode() if stdout else None,
                    stderr.decode() if stderr else None,
                )

            return result

        except asyncio.TimeoutError:
            logger.error(f"Subprocess timeout after {timeout}s: {cmd_str}")
            if process:
                process.kill()
            raise
        except Exception as e:
            logger.error(f"Subprocess execution failed: {cmd_str} - {e}")
            raise

    @staticmethod
    def run_sync(
        *args: str,
        cwd: Path | str | None = None,
        env: dict[str, str] | None = None,
        check: bool = False,
        timeout: float | None = None,
    ) -> subprocess.CompletedProcess[bytes]:
        """
        Execute a synchronous subprocess command with automatic debug logging.

        Args:
            *args: Command arguments
            cwd: Working directory
            env: Environment variables
            check: Whether to raise exception on non-zero exit code
            timeout: Timeout in seconds
            **kwargs: Additional arguments passed to subprocess.run

        Returns:
            subprocess.CompletedProcess object

        Raises:
            subprocess.CalledProcessError: If check=True and returncode != 0
            subprocess.TimeoutExpired: If timeout is exceeded
        """
        cmd_str = " ".join(args)
        logger.debug(f"Executing sync subprocess: {cmd_str}")
        if cwd:
            logger.debug(f"Working directory: {cwd}")

        # Set up capture_output by default
        cwd_arg = str(cwd) if cwd else None

        try:
            result = subprocess.run(args, check=check, capture_output=True, cwd=cwd_arg, env=env, timeout=timeout)

            # Log outputs at debug level
            if result.stdout:
                stdout_str = result.stdout.decode("utf-8", errors="replace")
                logger.debug(f"Subprocess stdout: {stdout_str}")
            if result.stderr:
                stderr_str = result.stderr.decode("utf-8", errors="replace")
                logger.debug(f"Subprocess stderr: {stderr_str}")

            return result

        except subprocess.TimeoutExpired:
            logger.error(f"Subprocess timeout after {timeout}s: {cmd_str}")
            raise
        except Exception as e:
            logger.error(f"Subprocess execution failed: {cmd_str} - {e}")
            raise

    @staticmethod
    async def run_with_realtime_output(
        *args: str,
        cwd: Path | str | None = None,
        env: dict[str, str] | None = None,
        progress_callback: Callable[..., Any] | None = None,
        max_buffer_lines: int | None = None,
    ) -> asyncio.subprocess.Process:
        """
        Execute a subprocess with real-time output streaming.

        Args:
            *args: Command arguments
            cwd: Working directory
            env: Environment variables
            progress_callback: Callback function for progress updates
            max_buffer_lines: Maximum number of lines to buffer for error logging.
                If None, buffers all lines (unbounded). If set, uses a ring buffer
                and only logs the last max_buffer_lines on error.
                Progress lines (containing \r, \b, or ANSI escapes) are deduplicated
                by overwriting the last progress line in the buffer.
            **kwargs: Additional arguments

        Returns:
            Process object after completion
        """
        cmd_str = " ".join(args)
        logger.debug(f"Executing subprocess with streaming: {cmd_str}")
        if cwd:
            logger.debug(f"Working directory: {cwd}")

        # Delegate streaming to iter_subprocess_lines to avoid duplicating logic.
        # We keep the previous behavior of merging stderr to stdout here.
        # Create the process here so we can return it (with .returncode) after streaming.
        proc_kwargs: dict[str, Any] = {}
        if cwd:
            proc_kwargs["cwd"] = str(cwd)
        if env:
            proc_kwargs["env"] = env

        process = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            **proc_kwargs,
        )

        # Use deque for bounded buffer if max_buffer_lines is set, else list for unbounded
        output_lines: deque[str] | list[str]
        if max_buffer_lines is not None:
            output_lines = deque(maxlen=max_buffer_lines)
        else:
            output_lines = []
        try:
            async for line, _source in SubprocessExecutor.iter_lines(process=process, encoding="utf-8"):
                # Check if this is a progress line
                if is_progress_line(line):
                    # If buffer is not empty and last line is also progress, replace it
                    if output_lines and is_progress_line(output_lines[-1]):
                        output_lines[-1] = line
                    else:
                        output_lines.append(line)
                else:
                    # Non-progress line: always append
                    output_lines.append(line)
                # use DEBUG level for per-line logs
                logger.debug(f"Subprocess: {line}")
                if progress_callback:
                    await progress_callback(line)

            # ensure process has exited and returncode is available
            await process.wait()

        except subprocess.CalledProcessError:
            # On failure, log the buffered output as error then re-raise
            # If using deque, it may not contain full output; note this in log
            full_output = "\n".join(output_lines)
            buffer_note = f" (last {max_buffer_lines} lines)" if max_buffer_lines is not None else ""
            logger.error(
                f"Subprocess failed with code {getattr(process, 'returncode', 'unknown')}: {cmd_str}{buffer_note}"
            )
            logger.error(f"Error output{buffer_note}: {full_output}")
            raise

        return process

    @staticmethod
    async def iter_lines(
        *args: str,
        process: asyncio.subprocess.Process | None = None,
        cwd: Path | str | None = None,
        env: dict[str, str] | None = None,
        merge_stderr: bool = True,
        encoding: str = "utf-8",
        errors: str = "replace",
    ) -> AsyncIterator[tuple[str, str]]:
        """
        Async generator that yields (line, source) tuples from a subprocess in real-time.

        Yields:
            Tuple[line, source] where source is 'stdout' or 'stderr'.

        Notes:
            - If `merge_stderr` is True, stderr is redirected to stdout and all yields
              will have source 'stdout'.
            - This generator streams lines as they are produced and does not buffer the
              entire output in memory. Callers can consume lines with `async for`.
            - If the subprocess exits with a non-zero code, a
              `subprocess.CalledProcessError` is raised after all lines are yielded.
        """
        # Build kwargs for subprocess
        proc_kwargs: dict[str, Any] = {}
        if cwd:
            proc_kwargs["cwd"] = str(cwd)
        if env:
            proc_kwargs["env"] = env

        # If caller provided a process, use it; otherwise create one from args.
        created_process = False
        if process is None:
            stderr_dest = asyncio.subprocess.STDOUT if merge_stderr else asyncio.subprocess.PIPE
            process = await asyncio.create_subprocess_exec(
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=stderr_dest,
                **proc_kwargs,
            )
            created_process = True

        # Use a sentinel to signal reader completion to avoid deadlocks
        sentinel = object()
        queue: asyncio.Queue[tuple[str, str] | object] = asyncio.Queue()

        async def _reader(stream: asyncio.StreamReader, source: str) -> None:
            try:
                async for raw in stream:
                    line = raw.decode(encoding, errors=errors).rstrip("\n\r")
                    await queue.put((line, source))
            except Exception as e:
                logger.error(f"Error reading from subprocess {source}: {e}")
            finally:
                await queue.put(sentinel)

        readers: list[asyncio.Task[Any]] = []
        if process.stdout:
            readers.append(asyncio.create_task(_reader(process.stdout, "stdout")))
        if not merge_stderr and process.stderr:
            readers.append(asyncio.create_task(_reader(process.stderr, "stderr")))

        active_readers = len(readers)

        try:
            while active_readers > 0:
                item = await queue.get()
                if item is sentinel:
                    active_readers -= 1
                else:
                    yield item  # type: ignore

            # ensure readers finished (they should be done if we got all sentinels)
            if readers:
                await asyncio.gather(*readers, return_exceptions=True)

            # If we created the process, wait for it. Otherwise, ensure returncode is set
            if created_process:
                await process.wait()
            elif process.returncode is None:
                # if caller passed a process we didn't create, wait briefly for exit
                await process.wait()

            # If process failed, raise after streaming all output
            if process.returncode is not None and process.returncode != 0:
                # prefer process.args when available
                proc_args = getattr(process, "args", args)
                raise subprocess.CalledProcessError(process.returncode, proc_args)

        finally:
            # best-effort cleanup
            for t in readers:
                if not t.done():
                    t.cancel()
