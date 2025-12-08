"""Configuration API endpoints."""

from fastapi import APIRouter, HTTPException

from leropilot.logger import get_logger
from leropilot.models.app_config import AppConfig
from leropilot.services.config import (
    get_config,
    reset_config_business_logic,
    update_config_business_logic,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/api/app-config", tags=["app-config"])


@router.get("", response_model=AppConfig)
async def get_current_config() -> AppConfig:
    """Get current application configuration.

    Returns:
        Current configuration
    """
    config = get_config()
    print(f"[API] Returning config with {len(config.repositories.lerobot_sources)} repos")
    print(f"[API] Repos: {[r.name for r in config.repositories.lerobot_sources]}")
    print(f"[API] Mirrors: {[m.name for m in config.pypi.mirrors]}")
    return config


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
        return await update_config_business_logic(config)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save config: {str(e)}") from e


@router.post("/reset", response_model=AppConfig)
async def reset_config() -> AppConfig:
    """Reset configuration to defaults, preserving data_dir if environments exist.

    Returns:
        Reset configuration
    """
    return await reset_config_business_logic()
