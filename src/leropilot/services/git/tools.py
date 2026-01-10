"""Git tool management service."""

import asyncio
import json
import os
import platform
import shutil
import tarfile
import tempfile
import traceback
import typing
import zipfile
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

import httpx

from leropilot.exceptions import OperationalError, ValidationError
from leropilot.logger import get_logger
from leropilot.services.config import get_config
from leropilot.services.i18n import get_i18n_service
from leropilot.utils import get_resources_dir
from leropilot.utils.subprocess_executor import SubprocessExecutor

logger = get_logger(__name__)


class GitToolManager:
    """Manages Git executable and bundled installation."""

    def __init__(self) -> None:
        pass

    def _get_message(self, key: str, lang: str = "en", **kwargs: object) -> str:
        """Get localized message."""
        i18n = get_i18n_service()
        # Use translate helper on i18n service (new domain app_settings.git)
        return i18n.translate(f"app_settings.git.{key}", lang=lang, default=key, **kwargs)

    def get_git_executable(self) -> str:
        """Get Git executable path based on configuration."""
        config = get_config()
        if config.tools.git.type == "custom" and config.tools.git.custom_path:
            return config.tools.git.custom_path

        if config.tools.git.type == "bundled":
            # Prioritize system git as per spec
            if shutil.which("git"):
                return "git"

            bundled_path = self.get_bundled_git_path()
            if bundled_path and bundled_path.exists():
                return str(bundled_path)

        # Fallback to system git
        return "git"

    def get_bundled_git_path(self) -> Path | None:
        """Get path to bundled git executable."""
        tools_dir = self.get_bundled_git_folder()

        system = platform.system().lower()
        if system == "windows":
            return tools_dir / "cmd" / "git.exe"
        elif system == "linux":
            return tools_dir / "bin" / "git"
        elif system == "darwin":
            return tools_dir / "bin" / "git"

        return None

    async def get_bundled_git_status(self) -> dict[str, Any]:
        """
        Get the status of bundled Git.

        Returns:
            Dictionary with installation status, path, and version
        """
        try:
            bundled_git = self.get_bundled_git_path()
            if not bundled_git:
                return {"installed": False, "message": "Bundled Git path not determined."}

            # Use validate_git_executable to check status
            validation = await self.validate_git_executable(bundled_git)

            if validation["valid"]:
                return {"installed": True, "path": str(bundled_git), "version": validation["version"]}
            else:
                # If it doesn't exist, it is not installed; this shouldn't be treated as an
                # error condition for the UI 'status' response.
                if validation["error"] == "Path does not exist":
                    return {"installed": False, "message": "Bundled Git is not installed."}
                return {"installed": False, "error": validation["error"]}
        except Exception as e:
            logger.error(f"Error checking bundled Git status: {e}")
            logger.debug(traceback.format_exc())
            return {"installed": False, "error": f"Error checking bundled Git status: {str(e)}"}

    async def validate_git_executable(self, path: Path) -> dict[str, Any]:
        """
        Validate a git executable path.

        Args:
            path: Path to git executable

        Returns:
            Dictionary with validation result
        """
        if not path.exists():
            return {"valid": False, "error": "Path does not exist"}

        if not path.is_file():
            return {"valid": False, "error": "Path is not a file"}

        if not os.access(path, os.X_OK):
            return {"valid": False, "error": "Path is not executable"}

        # Try to get version
        try:
            result = await SubprocessExecutor.run(str(path), "--version")

            if result.returncode != 0:
                error_msg = result.stderr.decode() if result.stderr else "Unknown error"
                return {"valid": False, "error": f"Failed to run git: {error_msg}"}

            version_output = result.stdout.decode().strip()
            # Expected output: "git version 2.x.x"
            return {"valid": True, "version": version_output}

        except Exception as e:
            return {"valid": False, "error": f"Error executing git: {str(e)}"}

    def get_bundled_git_folder(self) -> Path:
        config = get_config()
        assert config.paths.tools_dir is not None
        return config.paths.tools_dir / "git"

    async def install_bundled_git(
        self, progress_callback: Callable[[str, int], Awaitable[None]] | None = None, lang: str = "en"
    ) -> None:
        """
        Download and install bundled git.

        Args:
            progress_callback: Callback(status_msg, progress_percent)
            lang: Language code for localization
        """
        tools_dir = self.get_bundled_git_folder()
        tools_dir.mkdir(parents=True, exist_ok=True)

        # Load extra dependencies config
        resources_dir = get_resources_dir()
        with open(resources_dir / "environment_extra_dependencies.json", encoding="utf-8") as f:
            deps_config = json.load(f)

        system = platform.system().lower()
        machine = platform.machine().lower()

        # macOS: provide installation instructions instead
        if system == "darwin":
            raise ValidationError("app_settings.git.unsupported_macos")

        # Normalize machine name
        if machine in ["x86_64", "amd64"]:
            arch = "x86_64" if system != "windows" else "amd64"
        elif machine in ["aarch64", "arm64"]:
            arch = "arm64"
        else:
            raise OperationalError("app_settings.git.unsupported_arch", arch=machine)

        if system not in deps_config["git"]:
            raise OperationalError("app_settings.git.unsupported_os", os=system)

        if arch not in deps_config["git"][system]:
            raise OperationalError("app_settings.git.unsupported_arch_os", arch=arch, os=system)

        git_config = deps_config["git"][system][arch]
        url = git_config["url"]
        filename = git_config["filename"]
        download_path = tools_dir / filename

        logger.info(f"Downloading bundled git from {url}")
        if progress_callback:
            await progress_callback(self._get_message("downloading", lang), 0)

        # Download with progress using httpx
        async with httpx.AsyncClient(follow_redirects=True) as client:
            try:
                async with client.stream(
                    "GET", url, headers={"User-Agent": "Mozilla/5.0 (compatible; LeRoPilot/1.0)"}
                ) as response:
                    response.raise_for_status()
                    total_size = int(response.headers.get("Content-Length", 0))
                    block_size = 8192
                    downloaded_size = 0

                    with open(download_path, "wb") as out_file:
                        async for chunk in response.aiter_bytes(chunk_size=block_size):
                            out_file.write(chunk)
                            downloaded_size += len(chunk)

                            if total_size > 0:
                                percent = int((downloaded_size * 100) / total_size)
                                percent = min(90, percent)  # Cap at 90 for extraction
                                if progress_callback:
                                    await progress_callback(
                                        self._get_message("downloading_progress", lang, percent=percent), percent
                                    )
            except httpx.HTTPError as e:
                raise OperationalError("app_settings.git.download_failed", error=str(e), url=url) from e

        if progress_callback:
            await progress_callback(self._get_message("extracting", lang), 90)

        # Extract
        logger.info(f"Extracting {download_path} to {tools_dir}")
        await asyncio.to_thread(self._extract_archive, download_path, tools_dir)

        # Cleanup
        download_path.unlink()

        if progress_callback:
            await progress_callback(self._get_message("installed", lang), 100)

    def _extract_archive(self, file_path: Path, target_dir: Path) -> None:
        if str(file_path).endswith(".zip"):
            with zipfile.ZipFile(file_path, "r") as zip_ref:
                zip_ref.extractall(target_dir)
        elif str(file_path).endswith(".deb"):
            self._extract_deb(file_path, target_dir)
        elif str(file_path).endswith(".tar.bz2") or str(file_path).endswith(".tar.gz"):
            with tarfile.open(file_path, "r:*") as tar_ref:
                tar_ref.extractall(target_dir)
        else:
            raise OperationalError("app_settings.git.unsupported_format", filename=file_path.name)

    def _extract_deb(self, deb_path: Path, target_dir: Path) -> None:
        """Extract .deb package without sudo."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Try dpkg-deb first (cleaner)
            if shutil.which("dpkg-deb"):
                SubprocessExecutor.run_sync("dpkg-deb", "-x", str(deb_path), str(tmpdir_path), check=True)
            elif shutil.which("ar"):
                # Fallback to ar + tar
                SubprocessExecutor.run_sync("ar", "x", str(deb_path), cwd=str(tmpdir_path), check=True)

                # Find data.tar.*
                data_tar = None
                for f in tmpdir_path.glob("data.tar.*"):
                    data_tar = f
                    break

                if not data_tar:
                    raise OperationalError("app_settings.git.extract_failed_no_data", filename=deb_path.name)

                # Extract data.tar (supports .xz, .gz, .bz2)
                SubprocessExecutor.run_sync("tar", "xf", str(data_tar), "-C", str(tmpdir_path), check=True)
            else:
                raise OperationalError("app_settings.git.extract_failed_no_tools")

            # Move extracted files to target_dir
            # .deb packages usually extract to usr/bin, usr/lib, etc.
            # We want to flatten it to bin/, lib/ structure
            usr_dir = tmpdir_path / "usr"
            if usr_dir.exists():
                for item in usr_dir.iterdir():
                    dest = target_dir / item.name
                    if dest.exists():
                        if dest.is_dir():
                            shutil.rmtree(dest)
                        else:
                            dest.unlink()
                    shutil.move(str(item), str(dest))

    def ensure_git_installed(self) -> str:
        """
        Ensure Git is installed and return the executable path.

        Returns:
            Path to git executable

        Raises:
            ValueError: If Git is not installed or invalid
        """
        git_exec = self.get_git_executable()

        if git_exec == "git":
            if not shutil.which("git"):
                raise ValidationError("app_settings.git.not_found_in_path")
        else:
            if not Path(git_exec).exists() or not os.access(git_exec, os.X_OK):
                raise ValidationError("app_settings.git.invalid_path", path=git_exec)

        return git_exec

    def get_git_path(self) -> dict[str, str]:
        """
        Get the actual path to the git executable.

        Returns:
            Dictionary with 'path' key containing the git executable path

        Raises:
            ValueError: If Git not found in PATH
        """
        git_path = shutil.which("git")
        if git_path:
            return {"path": git_path}
        else:
            raise ResourceNotFoundError("app_settings.git.not_found_in_path")

    async def download_bundled_git_with_config_update(
        self, lang: str, config_updater: Callable[[], None]
    ) -> typing.AsyncGenerator[str, None]:
        """
        Download and install bundled Git with config update.

        Args:
            lang: Language for messages
            config_updater: Function to update config after installation

        Yields:
            Progress messages as SSE data
        """
        import asyncio

        queue: asyncio.Queue[str | None] = asyncio.Queue()

        async def callback(msg: str, percent: int) -> None:
            data = json.dumps({"message": msg, "progress": percent})
            await queue.put(f"data: {data}\n\n")

        async def run_install() -> None:
            try:
                await self.install_bundled_git(progress_callback=callback, lang=lang)

                # Update config to use bundled git
                config_updater()

                await queue.put("data: DONE\n\n")
            except Exception as e:
                await queue.put(f"data: ERROR: {str(e)}\n\n")
            finally:
                await queue.put(None)

        asyncio.create_task(run_install())

        while True:
            data = await queue.get()
            if data is None:
                break
            yield data
