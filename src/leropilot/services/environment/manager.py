"""Environment manager service."""

import json
import threading
from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from leropilot.logger import get_logger
from leropilot.exceptions import ResourceConflictError, ResourceNotFoundError
from leropilot.models.api.environment import EnvironmentListItem
from leropilot.models.environment import (
    EnvironmentConfig,
)

logger = get_logger(__name__)


class EnvironmentEntry(BaseModel):
    """Entry in the environments registry."""

    id: str
    name: str  # Directory name (unique, sanitized)
    display_name: str  # Human-readable name shown in UI
    status: Literal["pending", "installing", "ready", "error"] = "pending"
    created_at: datetime = Field(default_factory=datetime.now)
    error_message: str | None = None

    # Source info
    repo_id: str
    repo_url: str
    ref: str  # tag, branch, or commit

    # Python and torch versions
    python_version: str
    torch_version: str

    # Optional extras
    extras: list[str] = Field(default_factory=list)


class EnvironmentsData(BaseModel):
    """Root structure of environments.json."""

    environments: list[EnvironmentEntry] = []


class EnvironmentPathResolver:
    """
    Resolves environment paths using the registry.

    Combines PathsConfig with EnvironmentRegistry to resolve
    environment paths based on env_id -> name lookup.
    """

    def __init__(self, environments_dir: Path, registry: "EnvironmentManager") -> None:
        """
        Initialize the path resolver.

        Args:
            environments_dir: Base directory for environments
            registry: Environment registry instance
        """
        self.environments_dir = environments_dir
        self.registry = registry

    def get_environment_path(self, env_id: str) -> Path:
        """
        Get the environment directory path.

        Args:
            env_id: Environment ID

        Returns:
            Path to environment directory

        Raises:
            ValueError: If environment not found
        """
        entry = self.registry.get_by_id(env_id)
        if entry is None:
            raise ResourceNotFoundError("environment.instance.not_found", id=env_id)
        return self.environments_dir / entry.name

    def get_environment_venv_path(self, env_id: str) -> Path:
        """
        Get the virtual environment path.

        Args:
            env_id: Environment ID

        Returns:
            Path to virtual environment directory
        """
        return self.get_environment_path(env_id) / ".venv"

    def get_environment_bin_path(self, env_id: str) -> Path:
        """
        Get the binaries path for an environment.

        Args:
            env_id: Environment ID

        Returns:
            Path to binaries directory
        """
        import sys

        venv_path = self.get_environment_venv_path(env_id)
        return venv_path / ("Scripts" if sys.platform == "win32" else "bin")


class EnvironmentManager:
    """Manages environment lifecycle: creation, persistence, and retrieval."""

    def __init__(self) -> None:
        """Initialize environment manager."""
        from leropilot.services.config import get_config

        self.config = get_config()
        # Ensure the config provides environments_dir; mypy needs this asserted before assignment
        assert self.config.paths.environments_dir is not None
        self.environments_dir: Path = self.config.paths.environments_dir
        self.registry_file = self.environments_dir / "environments.json"
        self._data: EnvironmentsData | None = None
        self._file_lock = threading.Lock()

    def _load(self) -> EnvironmentsData:
        """Load data from disk."""
        if not self.registry_file.exists():
            return EnvironmentsData()

        try:
            with open(self.registry_file, encoding="utf-8") as f:
                data = json.load(f)
            return EnvironmentsData(**data)
        except Exception as e:
            logger.error(f"Failed to load environments.json: {e}")
            return EnvironmentsData()

    def _save(self) -> None:
        """Save data to disk."""
        if self._data is None:
            return

        try:
            self.environments_dir.mkdir(parents=True, exist_ok=True)
            with open(self.registry_file, "w", encoding="utf-8") as f:
                json.dump(self._data.model_dump(mode="json"), f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save environments.json: {e}")
            raise

    def _ensure_loaded(self) -> EnvironmentsData:
        """Ensure data is loaded into memory."""
        if self._data is None:
            self._data = self._load()
        return self._data

    def get_environment_path(self, env_id: str) -> Path:
        """
        Get the path to an environment directory.

        Args:
            env_id: Environment ID

        Returns:
            Path to the environment directory
        """
        entry = self.get_by_id(env_id)
        if entry is None:
            raise ResourceNotFoundError("environment.instance.not_found", id=env_id)
        return self.environments_dir / entry.name

    def get_environment_venv_path(self, env_id: str) -> Path:
        """
        Get the virtual environment path for an environment.

        Args:
            env_id: Environment ID

        Returns:
            Path to the virtual environment directory
        """
        return self.get_environment_path(env_id) / ".venv"

    def get_environment_bin_path(self, env_id: str) -> Path:
        """
        Get the binaries path for an environment.

        Args:
            env_id: Environment ID

        Returns:
            Path to the binaries directory
        """
        import sys

        venv_path = self.get_environment_venv_path(env_id)
        return venv_path / ("Scripts" if sys.platform == "win32" else "bin")

    def register(self, env_config: EnvironmentConfig) -> EnvironmentEntry:
        """
        Register a new environment.

        Args:
            env_config: Environment configuration

        Returns:
            The created environment entry

        Raises:
            ValueError: If an environment with the same ID or name already exists
        """
        with self._file_lock:
            data = self._ensure_loaded()

            # Check for duplicates
            if any(e.id == env_config.id for e in data.environments):
                raise ResourceConflictError("environment.instance.conflict_id", id=env_config.id)
            if any(e.name == env_config.name for e in data.environments):
                raise ResourceConflictError("environment.instance.conflict_name", name=env_config.name)

            entry = EnvironmentEntry(
                id=env_config.id,
                name=env_config.name,
                display_name=env_config.display_name,
                status="pending",
                created_at=env_config.created_at,
                repo_id=env_config.repo_id,
                repo_url=env_config.repo_url,
                ref=env_config.ref,
                python_version=env_config.python_version,
                torch_version=env_config.torch_version,
                extras=env_config.extras,
            )
            data.environments.append(entry)
            self._save()

            logger.info(f"Registered environment: id={env_config.id}, name={env_config.name}")
            return entry

    def unregister(self, env_id: str) -> bool:
        """
        Remove an environment from the registry.

        Args:
            env_id: Environment ID to remove

        Returns:
            True if removed, False if not found
        """
        with self._file_lock:
            data = self._ensure_loaded()

            original_count = len(data.environments)
            data.environments = [e for e in data.environments if e.id != env_id]

            if len(data.environments) < original_count:
                self._save()
                logger.info(f"Unregistered environment: {env_id}")
                return True

            return False

    def get_by_id(self, env_id: str) -> EnvironmentEntry | None:
        """
        Get an environment entry by ID.

        Args:
            env_id: Environment ID

        Returns:
            Environment entry or None if not found
        """
        data = self._ensure_loaded()
        return next((e for e in data.environments if e.id == env_id), None)

    def get_by_name(self, name: str) -> EnvironmentEntry | None:
        """
        Get an environment entry by name.

        Args:
            name: Environment name

        Returns:
            Environment entry or None if not found
        """
        data = self._ensure_loaded()
        return next((e for e in data.environments if e.name == name), None)

    def list_all_entries(self) -> list[EnvironmentEntry]:
        """
        List all registered environments.

        Returns:
            List of all environment entries
        """
        data = self._ensure_loaded()
        return list(data.environments)

    def update_status(
        self,
        env_id: str,
        status: Literal["pending", "installing", "ready", "error"],
        error_message: str | None = None,
    ) -> bool:
        """
        Update the status of an environment.

        Args:
            env_id: Environment ID
            status: New status
            error_message: Optional error message (for "error" status)

        Returns:
            True if updated, False if not found
        """
        with self._file_lock:
            data = self._ensure_loaded()

            entry = next((e for e in data.environments if e.id == env_id), None)
            if entry is None:
                return False

            entry.status = status
            entry.error_message = error_message
            self._save()

            logger.info(f"Updated environment status: {env_id} -> {status}")
            return True

    def update_python_version(self, env_id: str, python_version: str) -> bool:
        """
        Update the Python version of an environment.

        Args:
            env_id: Environment ID
            python_version: Actual Python version used in the virtual environment

        Returns:
            True if updated, False if not found
        """
        with self._file_lock:
            data = self._ensure_loaded()

            entry = next((e for e in data.environments if e.id == env_id), None)
            if entry is None:
                return False

            entry.python_version = python_version
            self._save()

            logger.info(f"Updated environment Python version: {env_id} -> {python_version}")
            return True

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
        env_dir = self.get_environment_path(env_config.id)
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
        entry = self.get_by_id(env_id)
        if entry is None:
            return None

        try:
            env_dir = self.get_environment_path(env_id)
        except ResourceNotFoundError:
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
        entries = self.list_all_entries()

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
        # Check if environment exists in registry
        entry = self.get_by_id(env_id)
        if entry is None:
            return False

        try:
            env_dir = self.get_environment_path(env_id)
        except ResourceNotFoundError:
            # Not in registry, but try to unregister anyway
            self.unregister(env_id)
            return False

        # Delete directory if it exists
        if env_dir.exists():
            import shutil

            shutil.rmtree(env_dir)
            logger.info(f"Deleted environment directory: {env_dir}")

        # Unregister from registry
        self.unregister(env_id)
        logger.info(f"Deleted environment: {env_id}")
        return True

    def register_environment(self, env_config: EnvironmentConfig) -> None:
        """
        Register a new environment in the registry.

        This should be called BEFORE creating the environment directory.

        Args:
            env_config: Environment configuration
        """
        self.register(env_config)

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
        return self.update_status(env_id, status, error_message)  # type: ignore

    def update_environment_python_version(self, env_id: str, python_version: str) -> bool:
        """
        Update the Python version of an environment in the registry.

        Args:
            env_id: Environment ID
            python_version: Actual Python version used in the virtual environment

        Returns:
            True if updated successfully
        """
        return self.update_python_version(env_id, python_version)
