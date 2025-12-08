"""
Installation configuration service.

This module handles loading and querying environment_installation_config.json, which defines:
- Repository configurations
- Version-specific settings (Python version, PyTorch version, etc.)
- Platform-specific installation steps
- Hardware compatibility matrices
"""

import json
from pathlib import Path

from leropilot.models.environment import EnvironmentConfig
from leropilot.models.installation import (
    EnvironmentInstallationConfig,
    VersionConfig,
)


class EnvironmentInstallationConfigService:
    """Service for loading and resolving installation configurations."""

    def __init__(self, config_file: Path) -> None:
        """
        Initialize config service.

        Args:
            config_file: Path to environment_installation_config.json
        """
        self.config_file = config_file
        # Import logger lazily to avoid circular imports
        from leropilot.logger import get_logger

        self._logger = get_logger(__name__)
        self._config: EnvironmentInstallationConfig | None = None
        self._load()

    def _load(self) -> None:
        """Load configuration from file."""
        try:
            if self.config_file.exists():
                with open(self.config_file, encoding="utf-8") as f:
                    data = json.load(f)
                self._config = EnvironmentInstallationConfig(**data)
                self._logger.info(f"Loaded installation config from {self.config_file}")
            else:
                self._logger.warning(f"Installation config file not found: {self.config_file}")
                # Create minimal default config
                self._config = EnvironmentInstallationConfig(repositories={})
        except Exception as e:
            self._logger.error(f"Failed to load installation config: {e}")
            self._config = EnvironmentInstallationConfig(repositories={})

    def get_config_for_env(self, env_config: EnvironmentConfig) -> VersionConfig | None:
        """
        Resolve configuration for an environment.
        """
        return self.get_version_config(env_config.repo_url, env_config.ref)

    def get_version_config(self, repo_url: str, ref: str) -> VersionConfig | None:
        """
        Resolve configuration for a repository and reference.

        Args:
            repo_url: Repository URL
            ref: Git reference (tag/branch)

        Returns:
            Resolved version configuration, or None if not found
        """
        if not self._config:
            self._logger.warning("No installation config loaded")
            return None

        # Step 1: Resolve repository
        repo_config = self._config.repositories.get(repo_url)
        if not repo_config:
            # Fallback to official
            repo_config = self._config.repositories.get("https://github.com/huggingface/lerobot.git")
            if not repo_config:
                self._logger.warning(f"No config found for repo {repo_url} or Lerobot official")
                return None

        # Step 2: Resolve version
        version_config = repo_config.versions.get(ref)
        if not version_config:
            # Try main branch as fallback
            version_config = repo_config.versions.get("main")
            if not version_config:
                self._logger.warning(f"No config found for version {ref} or main branch")
                return None
            # Only log if we are not just checking for existence (optional)
            # logger.info(f"Using main branch config as fallback for {repo_url}@{ref}")

        return version_config

    def reload(self) -> None:
        """Reload configuration from file."""
        self._load()
