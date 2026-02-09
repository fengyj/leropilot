"""Environment management services."""

from functools import lru_cache

# Export executor class (located in executor.py)
from .executor import EnvironmentInstallationExecutor
from .installation import EnvironmentInstallationPlanGenerator, InstallationManager
from .manager import EnvironmentEntry, EnvironmentManager
from .terminal import TerminalService


@lru_cache
def get_env_manager() -> EnvironmentManager:
    """Get or initialize environment manager (singleton)."""
    return EnvironmentManager()


__all__ = [
    "EnvironmentEntry",
    "EnvironmentManager",
    "InstallationManager",
    "EnvironmentInstallationPlanGenerator",
    "EnvironmentInstallationExecutor",
    "TerminalService",
    "get_env_manager",
]
