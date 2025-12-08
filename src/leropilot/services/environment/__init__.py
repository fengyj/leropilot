"""Environment management services."""

from functools import lru_cache

from .executor import EnvironmentInstallationExecutor
from .installation import EnvironmentInstallationPlanGenerator, InstallationManager
from .manager import EnvironmentManager
from .registry import (
    EnvironmentEntry,
    EnvironmentPathResolver,
    EnvironmentRegistry,
    get_path_resolver,
    get_registry,
)
from .terminal import TerminalService


@lru_cache
def get_env_manager() -> EnvironmentManager:
    """Get or initialize environment manager (singleton)."""
    return EnvironmentManager()


__all__ = [
    "EnvironmentEntry",
    "EnvironmentInstallationExecutor",
    "EnvironmentManager",
    "EnvironmentPathResolver",
    "EnvironmentRegistry",
    "InstallationManager",
    "EnvironmentInstallationPlanGenerator",
    "TerminalService",
    "get_env_manager",
    "get_path_resolver",
    "get_registry",
]
