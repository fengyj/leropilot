"""Git repository service."""

import subprocess
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from leropilot.exceptions import OperationalError, ResourceNotFoundError
from leropilot.logger import get_logger
from leropilot.models.app_config import AppConfig
from leropilot.services.i18n import get_i18n_service
from leropilot.utils.subprocess_executor import SubprocessExecutor

from .tools import GitToolManager

logger = get_logger(__name__)


class GitService:
    """Manages git repository operations."""

    def __init__(self, tool_manager: GitToolManager) -> None:
        self.tool_manager = tool_manager

    def resolve_repository_info(self, repo_id: str, config: AppConfig) -> tuple[str, Path]:
        """
        Resolve repository ID to URL and local path.

        Args:
            repo_id: Repository identifier
            config: Application configuration

        Returns:
            Tuple of (repo_url, repo_dir)

        Raises:
            ValueError: If repository not found
        """
        repo_url = None
        for source in config.repositories.lerobot_sources:
            if source.id == repo_id:
                repo_url = source.url
                break

        if not repo_url:
            raise ResourceNotFoundError("app_settings.lerobot_repository.not_found", id=repo_id)

        repo_dir = config.paths.get_repo_path(repo_id)
        return repo_url, repo_dir

    async def clone_or_update(
        self,
        repo_url: str,
        target_dir: Path,
        ref: str = "main",
        progress_callback: Callable[[str], Awaitable[None]] | None = None,
    ) -> str:
        """
        Clone repository or update if it exists.

        Args:
            repo_url: Repository URL
            target_dir: Target directory
            ref: Git ref (branch, tag, or commit)

        Returns:
            Commit hash

        Raises:
            Exception: If git operation fails
        """
        try:
            target_dir.mkdir(parents=True, exist_ok=True)

            # Check if directory already has a git repo
            git_dir = target_dir / ".git"

            if git_dir.exists():
                logger.info("Updating repository...")
                await self._update_repo(target_dir, ref, progress_callback)
            else:
                logger.info("Cloning repository...")
                await self._clone_repo(repo_url, target_dir, ref, progress_callback)

            # Get current commit hash
            commit_hash = await self._get_commit_hash(target_dir)
            logger.info(f"Current commit: {commit_hash}")

            return commit_hash
        except subprocess.CalledProcessError as e:
            raise OperationalError(
                "app_settings.git.failed", retriable=True, error=str(e), url=repo_url
            ) from e
        except Exception as e:
            if isinstance(e, AppBaseError):
                raise
            raise OperationalError(
                "app_settings.git.unexpected_error", retriable=False, error=str(e), url=repo_url
            ) from e

    async def _clone_repo(
        self,
        repo_url: str,
        target_dir: Path,
        ref: str,
        progress_callback: Callable[[str], Awaitable[None]] | None = None,
    ) -> None:
        """
        Clone repository with full history.

        Note: We do NOT use --depth 1 because we need to support switching
        between different versions (tags/branches) without re-downloading.
        """
        # Clone full repository (no --depth flag)
        # We clone the default branch first, then checkout the desired ref
        git_exec = self.tool_manager.get_git_executable()
        cmd = [git_exec, "clone", "--progress", repo_url, str(target_dir)]

        await SubprocessExecutor.run_with_realtime_output(*cmd, progress_callback=progress_callback)

        # After cloning, checkout the desired ref
        if ref not in ["main", "master"]:  # Skip if already on default branch
            await self._checkout_ref(target_dir, ref)

    async def _checkout_ref(self, repo_dir: Path, ref: str) -> None:
        """
        Checkout a specific ref (branch, tag, or commit).

        Args:
            repo_dir: Repository directory
            ref: Git ref to checkout
        """
        git_exec = self.tool_manager.get_git_executable()
        checkout_cmd = [git_exec, "checkout", ref]

        await SubprocessExecutor.run_with_realtime_output(*checkout_cmd, cwd=repo_dir)

    async def _update_repo(
        self,
        repo_dir: Path,
        ref: str,
        progress_callback: Callable[[str], Awaitable[None]] | None = None,
    ) -> None:
        """
        Update existing repository and checkout desired ref.

        Args:
            repo_dir: Repository directory
            ref: Git ref to checkout
            progress_callback: Optional callback for progress updates
        """
        # Fetch all refs (tags and branches)
        git_exec = self.tool_manager.get_git_executable()
        fetch_cmd = [git_exec, "fetch", "--all", "--tags"]

        await SubprocessExecutor.run_with_realtime_output(*fetch_cmd, cwd=repo_dir, progress_callback=progress_callback)

        # Checkout the desired ref
        await self._checkout_ref(repo_dir, ref)

        # If it's a branch, pull latest changes
        # Check if ref is a branch (not a tag or commit hash)
        is_branch = await self._is_branch(repo_dir, ref)
        if is_branch:
            git_exec = self.tool_manager.get_git_executable()
            pull_cmd = [git_exec, "pull", "--progress", "origin", ref]

            try:
                await SubprocessExecutor.run_with_realtime_output(
                    *pull_cmd, cwd=repo_dir, progress_callback=progress_callback
                )
            except subprocess.CalledProcessError:
                logger.warning(f"Git pull failed for branch {ref}, but continuing...")

    async def _is_branch(self, repo_dir: Path, ref: str) -> bool:
        """
        Check if ref is a branch.

        Args:
            repo_dir: Repository directory
            ref: Git ref

        Returns:
            True if ref is a branch
        """
        git_exec = self.tool_manager.get_git_executable()
        result = await SubprocessExecutor.run(git_exec, "show-ref", "--verify", f"refs/heads/{ref}", cwd=repo_dir)
        return result.returncode == 0

    async def _get_commit_hash(self, repo_dir: Path) -> str:
        """Get current commit hash."""
        git_exec = self.tool_manager.get_git_executable()
        result = await SubprocessExecutor.run(git_exec, "rev-parse", "HEAD", cwd=repo_dir)

        if result.returncode != 0:
            raise OperationalError("app_settings.git.failed_commit_hash", retriable=True, path=str(repo_dir))

        return result.stdout.decode().strip() if result.stdout else ""

    async def list_tags(self, repo_dir: Path) -> list[str]:
        """
        List all tags in repository.

        Args:
            repo_dir: Repository directory

        Returns:
            List of tag names
        """
        git_exec = self.tool_manager.get_git_executable()
        result = await SubprocessExecutor.run(git_exec, "tag", "-l", "--sort=-v:refname", cwd=repo_dir)

        if result.returncode != 0:
            return []

        tags = result.stdout.decode().strip().split("\n") if result.stdout else []
        return [tag for tag in tags if tag]

    async def list_branches(self, repo_dir: Path) -> list[str]:
        """
        List all remote branches.

        Args:
            repo_dir: Repository directory

        Returns:
            List of branch names
        """
        git_exec = self.tool_manager.get_git_executable()
        result = await SubprocessExecutor.run(git_exec, "branch", "-r", cwd=repo_dir)

        if result.returncode != 0:
            return []

        branches = []
        for line in result.stdout.decode().strip().split("\n") if result.stdout else []:
            # Remove "origin/" prefix and whitespace
            branch = line.strip().replace("origin/", "")
            if branch and "->" not in branch:  # Skip HEAD pointer
                branches.append(branch)

        return branches

    async def check_for_updates(self, repo_dir: Path) -> bool:
        """
        Check if the repository has updates available.

        Args:
            repo_dir: Repository directory

        Returns:
            True if updates are available, False otherwise
        """
        try:
            git_exec = self.tool_manager.get_git_executable()

            # First, fetch from remote
            await SubprocessExecutor.run(git_exec, "fetch", "origin", cwd=repo_dir)

            # Compare local and remote HEAD
            local_result = await SubprocessExecutor.run(git_exec, "rev-parse", "HEAD", cwd=repo_dir)
            local_commit = local_result.stdout.decode().strip() if local_result.stdout else ""

            # Get current branch
            branch_result = await SubprocessExecutor.run(git_exec, "rev-parse", "--abbrev-ref", "HEAD", cwd=repo_dir)
            current_branch = branch_result.stdout.decode().strip() if branch_result.stdout else ""

            # Get remote HEAD
            remote_result = await SubprocessExecutor.run(
                git_exec, "rev-parse", f"origin/{current_branch}", cwd=repo_dir
            )
            remote_commit = remote_result.stdout.decode().strip() if remote_result.stdout else ""

            # Check if they differ
            return local_commit != remote_commit

        except Exception as e:
            logger.warning(f"Failed to check for updates: {e}")
            return False

    async def get_repository_status(self, repo_id: str, config: AppConfig) -> dict[str, Any]:
        """
        Get the download status of a repository.

        Args:
            repo_id: Repository identifier
            config: Application configuration

        Returns:
            Dictionary with download status, last update time, cache path, and update availability
        """
        repo_dir = config.paths.get_repo_path(repo_id)
        git_dir = repo_dir / ".git"

        is_downloaded = git_dir.exists()
        last_updated: float | None = None
        has_updates = False

        if is_downloaded:
            # Get last modified time of .git directory
            try:
                last_updated = git_dir.stat().st_mtime
                last_updated_str = str(int(last_updated * 1000))  # Convert to milliseconds timestamp

                # Check if updates are available
                has_updates = await self.check_for_updates(repo_dir)

            except Exception as e:
                logger.warning(f"Failed to check for updates: {e}")

        return {
            "repo_id": repo_id,
            "is_downloaded": is_downloaded,
            "last_updated": last_updated_str if "last_updated_str" in locals() else None,
            "repo_path": str(repo_dir) if is_downloaded else None,
            "has_updates": has_updates,
        }
