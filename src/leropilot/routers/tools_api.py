"""Tools management API endpoints."""

import typing
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from leropilot.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/api/tools", tags=["tools"])


# Endpoints


@router.post("/git/validate")
async def validate_git_path(path_data: dict[str, str]) -> dict[str, Any]:
    """
    Validate a Git executable path.

    Args:
        path_data: Dictionary containing "path" key

    Returns:
        Validation result with version info
    """
    path_str = path_data.get("path")
    if not path_str:
        raise HTTPException(status_code=400, detail="Path is required")

    # If path is just a command name (like "git"), try to resolve it
    import shutil

    resolved_path = shutil.which(path_str)

    if resolved_path:
        path = Path(resolved_path)
    else:
        # If not found in PATH, treat as absolute/relative path
        path = Path(path_str)

    from leropilot.services.git import GitToolManager

    git_manager = GitToolManager()
    return await git_manager.validate_git_executable(path)


@router.get("/git/which")
async def get_git_path() -> dict[str, str]:
    """
    Get the actual path to the git executable.

    Returns:
        Dictionary with 'path' key containing the git executable path
    """
    from leropilot.services.git import GitToolManager

    git_manager = GitToolManager()
    try:
        return git_manager.get_git_path()
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.get("/git/bundled/status")
async def get_bundled_git_status() -> dict[str, Any]:
    """
    Get the status of bundled (system) Git.

    Returns:
        Dictionary with installation status, path, and version
    """
    from leropilot.services.git import GitToolManager

    git_manager = GitToolManager()
    return await git_manager.get_bundled_git_status()


@router.get("/git/bundled/download")
async def download_bundled_git() -> StreamingResponse:
    """
    Download and install bundled Git.
    """
    from leropilot.core.app_config import get_config

    config = get_config()
    lang = config.ui.preferred_language

    from leropilot.services.git import GitToolManager

    git_manager = GitToolManager()

    def config_updater() -> None:
        config = get_config()
        config.tools.git.type = "bundled"
        from leropilot.core.app_config import save_config

        save_config(config)

    async def event_generator() -> typing.AsyncGenerator[str, None]:
        async for data in git_manager.download_bundled_git_with_config_update(lang, config_updater):
            yield data

    return StreamingResponse(event_generator(), media_type="text/event-stream")
