"""
Unix-specific utilities: privilege helpers (pkexec/sudo wrapper) and UdevManager.

This module centralizes operations that may require elevated privileges and
provides safe, testable helpers for running commands with `pkexec` (or fallbacks)
and for installing udev rules atomically.

Notes on `pkexec` message support:
- `pkexec` itself does not provide a standardized `--message` flag that will
  be displayed to the authentication agent. Many desktop auth agents will show
  the program name and invoked action. To provide an explainer message in the
  GUI, we attempt to use `zenity` or `kdialog` if available by showing a small
  dialog then invoking the privileged command; if those are not available we
  fall back to running the command directly with `pkexec`/`sudo`.
"""
from __future__ import annotations

import shutil
import shlex
import logging
import os
import platform
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import TypeVar

from leropilot.utils.subprocess_executor import SubprocessExecutor

logger = logging.getLogger(__name__)

T = TypeVar("T")

# Configuration constants
UDEV_AUTO_INSTALL_ENV = "HARDWARE_UDEV_AUTO_INSTALL"
UDEV_RULES_FILE = "99-leropilot.rules"
UDEV_RULES_DIR = "/etc/udev/rules.d"


class PrivilegeHelper:
    """Helper to run commands with elevated privileges using pkexec (prefers)
    and falls back to sudo when pkexec is not available.

    The helper optionally accepts a short `message` which, if a GUI dialog
    tool (zenity/kdialog) is available, will be shown to the user before the
    privilege escalation prompt. This provides an explanation of why
    elevation is requested.
    """

    @staticmethod
    def _find_gui_dialog() -> str | None:
        # Preference order: zenity, kdialog
        if shutil.which("zenity"):
            return "zenity"
        if shutil.which("kdialog"):
            return "kdialog"
        return None

    @staticmethod
    def _pkexec_available() -> bool:
        return shutil.which("pkexec") is not None

    @staticmethod
    def _sudo_available() -> bool:
        return shutil.which("sudo") is not None

    @staticmethod
    def run_with_privilege(
        cmd: str | list[str],
        message: str | None = None,
        check: bool = True,
        timeout: float | None = None,
    ) -> subprocess.CompletedProcess[bytes]:
        """Run a command with privilege escalation.

        Args:
            cmd: command as list or shell string. If list, it is passed directly
                 to pkexec; if string, it will be executed via `sh -c` under pkexec
            message: optional message to show to the user (uses zenity/kdialog when available)
            check: whether to raise on non-zero exit
            timeout: optional timeout
        """
        # Prepare command string
        if isinstance(cmd, (list, tuple)):
            # Join safely for shell wrapped invocation
            safe_cmd = " ".join(shlex.quote(str(x)) for x in cmd)
        else:
            safe_cmd = str(cmd)

        dialog = PrivilegeHelper._find_gui_dialog()

        # If a dialog tool exists and a message was provided, wrap the command
        if message and dialog:
            # Use a shell wrapper that first displays a message then runs the real command
            if dialog == "zenity":
                dialog_cmd = f"zenity --info --no-wrap --text={shlex.quote(message)} --width=400"
            else:  # kdialog
                dialog_cmd = f"kdialog --msgbox {shlex.quote(message)}"
            wrapped = f"{dialog_cmd} && {safe_cmd}"
        else:
            wrapped = safe_cmd

        # Prefer pkexec if available
        if PrivilegeHelper._pkexec_available():
            full = ["pkexec", "bash", "-c", wrapped]
            logger.debug(f"Attempting privilege run via pkexec: {full}")
            return SubprocessExecutor.run_sync(*full, check=check, timeout=timeout)

        # Fall back to sudo if pkexec is not available
        if PrivilegeHelper._sudo_available():
            full = ["sudo", "sh", "-c", wrapped]
            logger.debug(f"Attempting privilege run via sudo: {full}")
            return SubprocessExecutor.run_sync(*full, check=check, timeout=timeout)

        # No privilege escalation tool found - raise
        raise RuntimeError("No privilege escalation tool (pkexec or sudo) available on system")


class UdevManager:
    """Manager for udev rule generation and installation.

    Usage:
        um = UdevManager()
        um.ensure_rule_present(...)
    """

    def __init__(self, rules_dir: Path | str = "/etc/udev/rules.d") -> None:
        self.rules_dir = Path(rules_dir)
        self.rules_dir.mkdir(parents=True, exist_ok=True)

    def generate_rule(
        self,
        subsystem: str = "video4linux",
        vendor: str | None = None,
        product: str | None = None,
        kernel: str | None = None,
        mode: str = "0660",
        group: str = "video",
    ) -> str:
        subsystem = subsystem or "video4linux"
        if subsystem == "video4linux":
            kernel_pat = kernel or "video*"
            base = f'SUBSYSTEM=="video4linux", KERNEL=="{kernel_pat}"'
        else:
            base = 'SUBSYSTEM=="tty"'
        attrs: list[str] = []
        if vendor:
            attrs.append(f'ATTRS{{idVendor}}=="{vendor}"')
        if product:
            attrs.append(f'ATTRS{{idProduct}}=="{product}"')
        attrs_str = (", " + ", ".join(attrs)) if attrs else ""
        rule = f"{base}{attrs_str}, MODE=\"{mode}\", GROUP=\"{group}\""
        return rule

    def _rule_file_path(self, filename: str = "99-leropilot.rules") -> Path:
        return self.rules_dir / filename

    def rule_exists(self, rule: str, filename: str = "99-leropilot.rules") -> bool:
        path = self._rule_file_path(filename)
        try:
            if not path.exists():
                return False
            content = path.read_text(encoding="utf-8")
            return rule.strip() in content
        except Exception as e:
            logger.debug(f"rule_exists failed: {e}")
            return False

    def install_rule_atomic(self, rule: str, filename: str = "99-leropilot.rules", use_pkexec: bool = True) -> None:
        path = self._rule_file_path(filename)
        # Compose content: existing content (if any) + our rule
        existing = ""
        if path.exists():
            try:
                existing = path.read_text(encoding="utf-8")
            except Exception:
                existing = ""

        content = (existing.rstrip() + "\n" if existing else "") + rule.strip() + "\n"

        # Write to a temp file in a writable temporary directory and move it atomically
        # Use system's temp dir; we then move with privileged helper if needed
        import tempfile

        with tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8") as tf:
            tf.write(content)
            tmp_path = Path(tf.name)

        # If the target file exists and is writable we can move directly
        try:
            if path.exists() and os.access(path, os.W_OK):
                tmp_path.replace(path)
                return
            # If the file does not exist but the directory is writable, write directly
            if not path.exists() and os.access(path.parent, os.W_OK):
                tmp_path.replace(path)
                return
        except Exception:
            # fall through to privileged move
            pass

        if use_pkexec:
            # Move the temp file to destination using pkexec (atomic using mv)
            dest = str(path)
            cmd = ["mv", shlex.quote(str(tmp_path)), shlex.quote(dest)]
            # We use a shell wrapper so we can run a compound command (mv && udevadm reload/trigger)
            shell_cmd = f"mv {shlex.quote(str(tmp_path))} {shlex.quote(dest)} && udevadm control --reload && udevadm trigger"
            PrivilegeHelper.run_with_privilege(shell_cmd, message="leropilot needs to install udev rules to access devices")
        else:
            raise PermissionError("Target udev rules file not writable and pkexec not allowed")

    def ensure_package_installed(self, package_name: str, message: str | None = None) -> bool:
        """Ensure a package (like `udev`) is installed. Attempts common package managers via pkexec.

        Returns True on success.
        """
        # Fast path: check for a binary associated with the package (udevadm)
        if shutil.which("udevadm"):
            return True

        # Try common package managers
        pkg_managers = [
            ("apt-get", f"apt-get update && apt-get install -y {shlex.quote(package_name)}"),
            ("dnf", f"dnf install -y {shlex.quote(package_name)}"),
            ("pacman", f"pacman -Syu --noconfirm {shlex.quote(package_name)}"),
            ("zypper", f"zypper install -y {shlex.quote(package_name)}"),
        ]

        for mgr, cmd in pkg_managers:
            if shutil.which(mgr):
                try:
                    PrivilegeHelper.run_with_privilege(cmd, message=message or f"Installing {package_name} is required")
                    return shutil.which("udevadm") is not None
                except Exception as e:
                    logger.debug(f"Package install attempt with {mgr} failed: {e}")
                    continue

        return False

    def ensure_rule_present(
        self,
        subsystem: str = "video4linux",
        vendor: str | None = None,
        product: str | None = None,
        kernel: str | None = None,
        mode: str | None = None,
        group: str | None = None,
        install_with_pkexec: bool = True,
        filename: str = "99-leropilot.rules",
    ) -> dict:
        path = self._rule_file_path(filename)
        used_group = group or ("video" if subsystem == "video4linux" else "dialout")
        used_mode = mode or ("0660" if subsystem == "video4linux" else "0666")
        rule = self.generate_rule(
            subsystem=subsystem,
            vendor=vendor,
            product=product,
            kernel=kernel,
            mode=used_mode,
            group=used_group,
        )

        if self.rule_exists(rule, filename=filename):
            return {"installed": False, "skipped": True, "rule": rule, "path": str(path)}

        # Ensure udev is present if we are operating on the system udev directory.
        # For non-system or test directories (e.g., temporary paths) we skip package checks
        # so tests and local operations can proceed without requiring `udevadm`.
        is_system_dir = os.name == "posix" and str(self.rules_dir).startswith("/etc/udev")
        if is_system_dir and not shutil.which("udevadm"):
            ok = self.ensure_package_installed("udev", message="leropilot requires udev to manage camera/serial devices")
            if not ok:
                return {"installed": False, "skipped": False, "rule": rule, "path": str(path)}

        # If we can write directly
        try:
            if path.exists() and os.access(path, os.W_OK):
                # append rule
                with path.open("a", encoding="utf-8") as fh:
                    fh.write(rule.strip() + "\n")
                SubprocessExecutor.run_sync("udevadm", "control", "--reload")
                SubprocessExecutor.run_sync("udevadm", "trigger")
                return {"installed": True, "skipped": False, "rule": rule, "path": str(path)}
        except Exception as e:
            logger.debug(f"Direct install failed: {e}")

        # Otherwise, try privileged atomic install
        try:
            self.install_rule_atomic(rule, filename=filename, use_pkexec=install_with_pkexec)
            return {"installed": True, "skipped": False, "rule": rule, "path": str(path)}
        except Exception as e:
            logger.debug(f"Privileged install failed: {e}")
            return {"installed": False, "skipped": False, "rule": rule, "path": str(path)}

    def ensure_device_access_with_retry(
        self,
        device_path: str,
        open_func: Callable[[], T | None],
        subsystem: str = "tty",
        vendor: str | None = None,
        product: str | None = None,
    ) -> T | None:
        """Try to open a device, auto-fix permissions if needed, and retry once.

        Args:
            device_path: Device path (e.g., /dev/ttyUSB0, /dev/video0)
            open_func: Callable that attempts to open the device, returns object on success or None on failure
            subsystem: Device subsystem ("tty" or "video4linux")
            vendor: Optional USB vendor ID (hex string like "1234")
            product: Optional USB product ID (hex string like "abcd")

        Returns:
            Result from open_func if successful, None otherwise

        Example:
            >>> cap = udev_manager.ensure_device_access_with_retry(
            ...     "/dev/video0",
            ...     lambda: cv2.VideoCapture(0) if cv2.VideoCapture(0).isOpened() else None,
            ...     subsystem="video4linux"
            ... )
        """
        # First attempt
        result = open_func()
        if result is not None:
            return result

        # Check if this looks like a permission issue on Linux
        if platform.system() != "Linux":
            return None

        if not os.path.exists(device_path):
            logger.debug(f"Device {device_path} does not exist")
            return None

        if os.access(device_path, os.R_OK | os.W_OK):
            # Device exists and is accessible, but open_func failed for other reasons
            return None

        # Permission issue detected - try to fix
        logger.info(f"Permission issue detected for {device_path}, attempting udev rule installation")

        # Check environment variable for auto-install preference
        auto_install_env = os.getenv(UDEV_AUTO_INSTALL_ENV, "true").lower()
        auto_install = auto_install_env in ("1", "true", "yes")

        try:
            result_dict = self.ensure_rule_present(
                subsystem=subsystem,
                vendor=vendor,
                product=product,
                install_with_pkexec=auto_install,
            )
            if not result_dict.get("installed") and not result_dict.get("skipped"):
                logger.warning(f"Failed to install udev rule for {device_path}")
                return None
        except Exception as e:
            logger.debug(f"Exception during udev rule installation: {e}")
            return None

        # Retry open after permission fix
        logger.debug(f"Retrying device open after permission fix: {device_path}")
        return open_func()
