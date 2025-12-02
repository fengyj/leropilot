"""Environment manager service."""

import json
from pathlib import Path

from leropilot.logger import get_logger
from leropilot.models.environment import EnvironmentConfig

logger = get_logger(__name__)


class EnvironmentManager:
    """Manages environment lifecycle: creation, persistence, and retrieval."""

    def __init__(self) -> None:
        """Initialize environment manager."""
        from leropilot.core.app_config import get_config

        self.config = get_config()
        # Ensure the config provides environments_dir; mypy needs this asserted before assignment
        assert self.config.paths.environments_dir is not None
        self.environments_dir: Path = self.config.paths.environments_dir

    def create_environment_directory(self, env_dir: Path) -> None:
        """
        Create directory structure for an environment.

        Note: Repository code is NOT stored here. It's in global cache.

        Args:
            env_dir: Environment directory path
        """
        env_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Created environment directory: {env_dir}")

    def save_environment_config(self, env_config: EnvironmentConfig) -> None:
        """
        Save environment configuration to disk.

        Args:
            env_config: Environment configuration
        """
        env_dir = self.environments_dir / env_config.id
        config_file = env_dir / "config.json"

        with open(config_file, "w", encoding="utf-8") as f:
            json.dump(env_config.model_dump(mode="json"), f, indent=2, ensure_ascii=False)

        logger.info(f"Saved environment config: {config_file}")

    def load_environment_config(self, env_id: str) -> EnvironmentConfig | None:
        """
        Load environment configuration from disk.

        Args:
            env_id: Environment ID

        Returns:
            Environment configuration or None if not found
        """
        config_file = self.environments_dir / env_id / "config.json"
        if not config_file.exists():
            return None

        with open(config_file, encoding="utf-8") as f:
            data = json.load(f)

        return EnvironmentConfig(**data)

    def list_environments(self) -> list[EnvironmentConfig]:
        """
        List all environments.

        Returns:
            List of environment configurations
        """
        if not self.environments_dir.exists():
            return []

        environments = []
        for env_dir in self.environments_dir.iterdir():
            if env_dir.is_dir():
                env_config = self.load_environment_config(env_dir.name)
                if env_config:
                    environments.append(env_config)

        return environments

    def delete_environment(self, env_id: str) -> bool:
        """
        Delete an environment.

        Args:
            env_id: Environment ID

        Returns:
            True if deleted successfully
        """
        env_dir = self.environments_dir / env_id
        if not env_dir.exists():
            return False

        import shutil

        shutil.rmtree(env_dir)
        logger.info(f"Deleted environment: {env_id}")
        return True
