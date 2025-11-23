"""Configuration API endpoints."""

import shutil
from pathlib import Path

from fastapi import APIRouter, HTTPException

from leropilot.config import get_config, reload_config, save_config
from leropilot.models.config import AppConfig

router = APIRouter(prefix="/api/config", tags=["config"])


async def migrate_data_directory(old_dir: Path, new_dir: Path) -> None:
    """Migrate data from old directory to new directory.

    Args:
        old_dir: Old data directory
        new_dir: New data directory

    Raises:
        ValueError: If migration fails
    """
    if not old_dir.exists():
        # Nothing to migrate
        return

    # Create new directory
    new_dir.mkdir(parents=True, exist_ok=True)

    # Migrate subdirectories (not environments, as it should be empty before first env)
    subdirs = ["logs", "cache", "repos"]

    for subdir_name in subdirs:
        old_subdir = old_dir / subdir_name
        new_subdir = new_dir / subdir_name

        if old_subdir.exists():
            if new_subdir.exists():
                # Merge: copy contents
                shutil.copytree(old_subdir, new_subdir, dirs_exist_ok=True)
            else:
                # Move entire directory
                shutil.move(str(old_subdir), str(new_subdir))

    # Clean up old directory if it's empty
    try:
        if old_dir.exists() and not any(old_dir.iterdir()):
            old_dir.rmdir()
    except OSError:
        # Directory not empty or other error, leave it
        pass


async def check_has_environments() -> bool:
    """Check if any environments have been created.

    Returns:
        True if environments exist, False otherwise
    """
    config = get_config()
    env_dir = config.paths.environments_dir

    if not env_dir or not env_dir.exists():
        return False

    # Check if any subdirectories exist
    return any(env_dir.iterdir())


@router.get("", response_model=AppConfig)
async def get_current_config() -> AppConfig:
    """Get current application configuration.

    Returns:
        Current configuration
    """
    return get_config()


@router.get("/has-environments")
async def get_has_environments() -> dict[str, bool]:
    """Check if any environments have been created.

    Returns:
        Dictionary with has_environments boolean
    """
    has_envs = await check_has_environments()
    return {"has_environments": has_envs}


@router.put("", response_model=AppConfig)
async def update_config(config: AppConfig) -> AppConfig:
    """Update application configuration with validation and data migration.

    Args:
        config: New configuration

    Returns:
        Updated configuration

    Raises:
        HTTPException: If config save fails or data_dir change is invalid
    """
    try:
        # Get current config to check if data_dir is being changed
        current_config = get_config()

        # Check if data_dir is being changed
        if current_config.paths.data_dir != config.paths.data_dir:
            # Check if environments exist
            has_envs = await check_has_environments()
            if has_envs:
                raise HTTPException(
                    status_code=400,
                    detail="Cannot change data directory after environments have been created. "
                    "This is to prevent data loss and ensure data integrity.",
                )

            # Migrate existing data
            try:
                await migrate_data_directory(current_config.paths.data_dir, config.paths.data_dir)
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Failed to migrate data: {str(e)}") from e

        save_config(config)
        return reload_config()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save config: {str(e)}") from e


@router.post("/reset", response_model=AppConfig)
async def reset_config() -> AppConfig:
    """Reset configuration to defaults, preserving data_dir if environments exist.

    Returns:
        Reset configuration
    """
    current_config = get_config()

    # Check if environments exist
    has_envs = await check_has_environments()

    # Create default config
    default_config = AppConfig()

    # Preserve data_dir if environments exist
    if has_envs:
        default_config.paths.data_dir = current_config.paths.data_dir
        default_config.paths.model_post_init(None)

    save_config(default_config)
    return reload_config()


@router.post("/reload", response_model=AppConfig)
async def reload_configuration() -> AppConfig:
    """Reload configuration from file.

    Returns:
        Reloaded configuration
    """
    return reload_config()
