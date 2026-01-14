"""Repository management API endpoints."""

import asyncio
from collections.abc import AsyncGenerator

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from leropilot.exceptions import ResourceNotFoundError
from leropilot.logger import get_logger
from leropilot.models.api.repository import (
    RepositoryInfo,
    RepositoryStatus,
    VersionCompatibilityEntry,
    VersionInfo,
)
from leropilot.services.config import EnvironmentInstallationConfigService, get_config
from leropilot.services.git import GitService, GitToolManager
from leropilot.services.hardware import GPUDetector
from leropilot.utils import get_resources_dir

logger = get_logger(__name__)
router = APIRouter(prefix="/api/repositories", tags=["repositories"])

# Initialize services (will be properly initialized on startup)
_config_service: EnvironmentInstallationConfigService | None = None
_gpu_detector: GPUDetector | None = None


def get_services() -> tuple[EnvironmentInstallationConfigService, GPUDetector]:
    """Get or initialize services."""
    global _config_service, _gpu_detector

    if not _config_service:
        resources_dir = get_resources_dir()
        _config_service = EnvironmentInstallationConfigService(resources_dir / "environment_installation_config.json")
        _gpu_detector = GPUDetector()

    assert _config_service is not None
    assert _gpu_detector is not None
    return _config_service, _gpu_detector


# Request/Response Models


# Endpoints


@router.get("", response_model=list[RepositoryInfo])
async def get_repositories() -> list[RepositoryInfo]:
    """
    Get available repositories from configuration.

    Returns:
        List of repository information
    """
    config = get_config()
    repos = []

    for source in config.repositories.lerobot_sources:
        repos.append(
            RepositoryInfo(
                id=source.id,
                name=source.name,
                url=source.url,
                is_default=source.is_default,
            )
        )

    return repos


@router.get("/{repo_id}/versions", response_model=list[VersionInfo])
async def get_repository_versions(repo_id: str) -> list[VersionInfo]:
    """
    Get available versions (tags/branches) for a repository.
    """
    from leropilot.services.git import GitService, GitToolManager

    config = get_config()

    # Find repository URL
    repo_url = None
    for source in config.repositories.lerobot_sources:
        if source.id == repo_id:
            repo_url = source.url
            break

    if not repo_url:
        raise ResourceNotFoundError("app_settings.lerobot_repository.not_found", id=repo_id)

    # Check if we have a cached clone
    repo_dir = config.paths.get_repo_path(repo_id)
    tool_manager = GitToolManager()
    git_manager = GitService(tool_manager)

    # Get services
    config_service, gpu_detector = get_services()
    gpu_info = gpu_detector.detect()

    # Clone or update repository (shallow clone for speed)
    if not repo_dir.exists():
        await git_manager.clone_or_update(repo_url, repo_dir, "main")

    # Get tags and branches
    tags = await git_manager.list_tags(repo_dir)
    branches = await git_manager.list_branches(repo_dir)

    # Combine and format
    versions = []

    def build_version_info(ref_name: str, is_stable: bool) -> VersionInfo:
        ver_config = config_service.get_version_config(repo_url, ref_name)
        torch_ver = ver_config.torch_version if ver_config else None
        python_ver = ver_config.python_version if ver_config else None

        compat_matrix = []
        if ver_config and ver_config.compatibility_matrix:
            # Determine recommendation
            recommended_idx = 0

            # Find best match for hardware
            for i, entry in enumerate(ver_config.compatibility_matrix):
                if gpu_info.has_nvidia_gpu and entry.cuda:
                    recommended_idx = i
                    break
                if gpu_info.has_amd_gpu and entry.rocm:
                    recommended_idx = i
                    break

            for i, entry in enumerate(ver_config.compatibility_matrix):
                compat_matrix.append(
                    VersionCompatibilityEntry(
                        torch=entry.torch,
                        cuda=entry.cuda,
                        rocm=entry.rocm,
                        cpu=entry.cpu,
                        torchvision=entry.torchvision,
                        torchaudio=entry.torchaudio,
                        is_recommended=(i == recommended_idx),
                    )
                )

        return VersionInfo(
            tag=ref_name,
            is_stable=is_stable,
            python_version=python_ver,
            torch_version=torch_ver,
            compatibility_matrix=compat_matrix,
        )

    # Add tags (stable versions)
    for tag in tags:
        versions.append(build_version_info(tag, True))

    # Add main branches (unstable)
    for branch in ["main", "master", "develop"]:
        if branch in branches:
            versions.append(build_version_info(branch, False))

    return versions


@router.get("/{repo_id}/status", response_model=RepositoryStatus)
async def get_repository_status(repo_id: str) -> RepositoryStatus:
    """
    Get the download status of a repository.

    Returns:
        Dictionary with download status, last update time, cache path, and update availability
    """
    config = get_config()
    tool_manager = GitToolManager()
    git_manager = GitService(tool_manager)
    status_dict = await git_manager.get_repository_status(repo_id, config)
    return RepositoryStatus(**status_dict)


@router.get("/{repo_id}/download")
async def stream_download_repository(repo_id: str) -> StreamingResponse:
    """
    Stream download progress for a repository.
    """

    config = get_config()
    tool_manager = GitToolManager()
    git_manager = GitService(tool_manager)

    try:
        repo_url, repo_dir = git_manager.resolve_repository_info(repo_id, config)
        tool_manager.ensure_git_installed()
    except ValueError as e:
        error_message = str(e)

        async def error_gen() -> AsyncGenerator[str, None]:
            yield f"data: ERROR: {error_message}\n\n"

        return StreamingResponse(error_gen(), media_type="text/event-stream")

    async def event_generator() -> AsyncGenerator[str, None]:
        queue: asyncio.Queue[str | None] = asyncio.Queue()

        async def callback(line: str) -> None:
            await queue.put(f"data: {line}\n\n")

        async def run_git() -> None:
            try:
                await git_manager.clone_or_update(
                    repo_url=repo_url, target_dir=repo_dir, ref="main", progress_callback=callback
                )
                await queue.put("data: DONE\n\n")
            except Exception as e:
                await queue.put(f"data: ERROR: {str(e)}\n\n")
            finally:
                await queue.put(None)  # Sentinel

        # Start git task
        asyncio.create_task(run_git())

        while True:
            data = await queue.get()
            if data is None:
                break
            yield data

    return StreamingResponse(event_generator(), media_type="text/event-stream")
