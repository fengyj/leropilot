"""Environment manager service."""

import json
from pathlib import Path

from leropilot.logger import get_logger
from leropilot.models.api.environment import EnvironmentListItem
from leropilot.models.environment import EnvironmentConfig

from .registry import get_path_resolver, get_registry

logger = get_logger(__name__)


class EnvironmentManager:
    """Manages environment lifecycle: creation, persistence, and retrieval."""

    def __init__(self) -> None:
        """Initialize environment manager."""
        from leropilot.services.config import get_config

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

        Saves to both config.json (for direct access) and updates installation_state.json
        (if it exists) to keep them in sync.

        Args:
            env_config: Environment configuration
        """
        path_resolver = get_path_resolver()
        env_dir = path_resolver.get_environment_path(env_config.id)
        config_file = env_dir / "config.json"
        state_file = env_dir / "installation_state.json"

        # Save to config.json
        with open(config_file, "w", encoding="utf-8") as f:
            json.dump(env_config.model_dump(mode="json"), f, indent=2, ensure_ascii=False)

        # Update installation_state.json if it exists
        if state_file.exists():
            with open(state_file, encoding="utf-8") as f:
                state_data = json.load(f)
            state_data["env_config"] = env_config.model_dump(mode="json")
            with open(state_file, "w", encoding="utf-8") as f:
                json.dump(state_data, f, indent=2, ensure_ascii=False)

        logger.info(f"Saved environment config: {config_file}")

    def load_environment_config(self, env_id: str) -> EnvironmentConfig | None:
        """
        Load environment configuration from disk.

        Tries to load from config.json first, then falls back to installation_state.json.

        Args:
            env_id: Environment ID

        Returns:
            Environment configuration or None if not found
        """
        # First check if environment exists in registry
        registry = get_registry()
        entry = registry.get_by_id(env_id)
        if entry is None:
            return None

        path_resolver = get_path_resolver()
        try:
            env_dir = path_resolver.get_environment_path(env_id)
        except ValueError:
            return None

        config_file = env_dir / "config.json"
        state_file = env_dir / "installation_state.json"

        # Try config.json first
        if config_file.exists():
            with open(config_file, encoding="utf-8") as f:
                data = json.load(f)
            return EnvironmentConfig(**data)

        # Fall back to installation_state.json
        if state_file.exists():
            with open(state_file, encoding="utf-8") as f:
                state_data = json.load(f)
            if "env_config" in state_data:
                return EnvironmentConfig(**state_data["env_config"])

        return None

    def list_environments(self) -> list[EnvironmentListItem]:
        """
        List all environments from the registry.

        Returns:
            List of environment data for the UI
        """
        registry = get_registry()
        entries = registry.list_all()

        environments = []
        for entry in entries:
            environments.append(
                EnvironmentListItem(
                    id=entry.id,
                    name=entry.name,
                    display_name=entry.display_name,
                    repo_id=entry.repo_id,
                    repo_url=entry.repo_url,
                    ref=entry.ref,
                    python_version=entry.python_version,
                    torch_version=entry.torch_version,
                    status=entry.status,
                    error_message=entry.error_message,
                )
            )

        return environments

    def delete_environment(self, env_id: str) -> bool:
        """
        Delete an environment.

        Removes the environment directory and unregisters from registry.

        Args:
            env_id: Environment ID

        Returns:
            True if deleted successfully
        """
        registry = get_registry()
        path_resolver = get_path_resolver()

        # Check if environment exists in registry
        entry = registry.get_by_id(env_id)
        if entry is None:
            return False

        try:
            env_dir = path_resolver.get_environment_path(env_id)
        except ValueError:
            # Not in registry, but try to unregister anyway
            registry.unregister(env_id)
            return False

        # Delete directory if it exists
        if env_dir.exists():
            import shutil

            shutil.rmtree(env_dir)
            logger.info(f"Deleted environment directory: {env_dir}")

        # Unregister from registry
        registry.unregister(env_id)
        logger.info(f"Deleted environment: {env_id}")
        return True

    def register_environment(self, env_config: EnvironmentConfig) -> None:
        """
        Register a new environment in the registry.

        This should be called BEFORE creating the environment directory.

        Args:
            env_config: Environment configuration
        """
        registry = get_registry()
        registry.register(env_config)
        logger.info(f"Registered environment: id={env_config.id}, name={env_config.name}")

    def update_environment_status(
        self,
        env_id: str,
        status: str,
        error_message: str | None = None,
    ) -> bool:
        """
        Update the status of an environment in the registry.

        Args:
            env_id: Environment ID
            status: New status
            error_message: Optional error message

        Returns:
            True if updated successfully
        """
        registry = get_registry()
        return registry.update_status(env_id, status, error_message)  # type: ignore

    def update_environment_python_version(self, env_id: str, python_version: str) -> bool:
        """
        Update the Python version of an environment in the registry.

        Args:
            env_id: Environment ID
            python_version: Actual Python version used in the virtual environment

        Returns:
            True if updated successfully
        """
        registry = get_registry()
        return registry.update_python_version(env_id, python_version)
