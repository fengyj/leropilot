"""Terminal service for opening system terminals with environment activation."""

import os
import platform
import shutil
import subprocess
from pathlib import Path

from leropilot.logger import get_logger

logger = get_logger(__name__)


class TerminalService:
    """Service for opening system terminals with virtual environment activation."""

    @staticmethod
    def open_terminal(env_dir: Path, venv_path: Path) -> None:
        """
        Open a system terminal in the environment directory with venv activated.

        Args:
            env_dir: Environment directory path
            venv_path: Virtual environment path

        Raises:
            FileNotFoundError: If environment or venv directory doesn't exist
            RuntimeError: If terminal cannot be opened
        """
        if not env_dir.exists():
            raise FileNotFoundError(f"Environment directory not found: {env_dir}")

        if not venv_path.exists():
            raise FileNotFoundError(f"Virtual environment not found: {venv_path}")

        system = platform.system()

        try:
            if system == "Windows":
                TerminalService._open_windows_terminal(env_dir, venv_path)
            elif system == "Darwin":
                TerminalService._open_macos_terminal(env_dir, venv_path)
            elif system == "Linux":
                # Check if running in WSL
                if TerminalService._is_wsl():
                    TerminalService._open_wsl_terminal(env_dir, venv_path)
                else:
                    TerminalService._open_linux_terminal(env_dir, venv_path)
            else:
                raise RuntimeError(f"Unsupported operating system: {system}")

        except subprocess.SubprocessError as e:
            logger.error(f"Failed to open terminal: {e}")
            raise RuntimeError(f"Failed to open terminal: {str(e)}") from e

    @staticmethod
    def _open_windows_terminal(env_dir: Path, venv_path: Path) -> None:
        """Open cmd.exe terminal on Windows."""
        activate_script = venv_path / "Scripts" / "activate.bat"

        # Use 'start' command to ensure a new window is opened.
        # Format: start "Title" /D "WorkingDir" cmd /k "Command"
        # We need to quote paths to handle spaces.
        # Note: The first quoted argument to 'start' is always interpreted as the window title.
        cmd = f'start "LeRoPilot Terminal" /D "{env_dir}" cmd /k "{activate_script}"'

        # shell=True is required to use the 'start' command (which is a shell builtin)
        subprocess.Popen(
            cmd,
            shell=True,
        )

    @staticmethod
    def _open_macos_terminal(env_dir: Path, venv_path: Path) -> None:
        """Open Terminal.app on macOS using AppleScript."""
        activate_script = venv_path / "bin" / "activate"
        script = f'tell application "Terminal" to do script "cd {env_dir} && source {activate_script}"'

        subprocess.Popen(
            ["osascript", "-e", script],
            start_new_session=True,
        )

    @staticmethod
    def _open_linux_terminal(env_dir: Path, venv_path: Path) -> None:
        """Open terminal on Linux."""
        terminal = TerminalService._find_linux_terminal()

        if not terminal:
            raise RuntimeError("No terminal emulator found. Please set $TERMINAL environment variable.")

        # Construct command to activate venv
        activate_script = venv_path / "bin" / "activate"
        shell_cmd = f'cd "{env_dir}" && source "{activate_script}" && exec bash'

        # Most terminals support -e flag for command execution
        # Use -e instead of -- for better compatibility
        subprocess.Popen(
            [terminal, "-e", "bash", "-c", shell_cmd],
            start_new_session=True,
        )

    @staticmethod
    def _find_linux_terminal() -> str | None:
        """Find available terminal emulator on Linux."""
        # Check $TERMINAL environment variable
        if "TERMINAL" in os.environ:
            return os.environ["TERMINAL"]

        # Try common terminals in order of preference
        for term in ["x-terminal-emulator", "gnome-terminal", "konsole", "xfce4-terminal", "xterm"]:
            if shutil.which(term):
                return term

        return None

    @staticmethod
    def _is_wsl() -> bool:
        """Check if running in WSL (Windows Subsystem for Linux)."""
        try:
            with open("/proc/version") as f:
                return "microsoft" in f.read().lower()
        except Exception:
            return False

    @staticmethod
    def _open_wsl_terminal(env_dir: Path, venv_path: Path) -> None:
        """Open Windows Terminal in WSL environment."""
        # In WSL, we can use wt.exe (Windows Terminal) to open a new tab
        activate_script = venv_path / "bin" / "activate"

        # Convert WSL path to Windows path for wt.exe
        # wt.exe expects the command to run in WSL
        shell_cmd = f'cd "{env_dir}" && source "{activate_script}" && exec bash'

        # Try to use wt.exe (Windows Terminal)
        wt_path = shutil.which("wt.exe")
        if wt_path:
            # Use wt.exe to open a new tab in Windows Terminal
            subprocess.Popen(
                ["wt.exe", "-w", "0", "new-tab", "bash", "-c", shell_cmd],
                start_new_session=True,
            )
        else:
            # Fallback: try cmd.exe
            cmd_path = shutil.which("cmd.exe")
            if cmd_path:
                # Use cmd.exe to start bash in WSL
                subprocess.Popen(
                    ["cmd.exe", "/c", "start", "bash", "-c", shell_cmd],
                    start_new_session=True,
                )
            else:
                raise RuntimeError(
                    "No suitable terminal found in WSL. Please install Windows Terminal or ensure cmd.exe is available."
                )
