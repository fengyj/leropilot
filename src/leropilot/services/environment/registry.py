"""Environment registry service.

Manages environments.json as the central registry for all environments.
Provides caching and path resolution functionality.
"""

import json
import threading
from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from leropilot.exceptions import ResourceConflictError, ResourceNotFoundError
from leropilot.logger import get_logger
from leropilot.models.environment import EnvironmentConfig

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


class EnvironmentRegistry:
    """
    Central registry for managing environments.

    Maintains an in-memory cache of environments.json data.
    All modifications are immediately persisted to disk.
    """

    _instance: "EnvironmentRegistry | None" = None
    _lock = threading.Lock()

    def __init__(self, environments_dir: Path) -> None:
        """
        Initialize the registry.

        Args:
            environments_dir: Path to the environments directory
        """
        self.environments_dir = environments_dir
        self.registry_file = environments_dir / "environments.json"
        self._data: EnvironmentsData | None = None
        self._file_lock = threading.Lock()

    @classmethod
    def get_instance(cls, environments_dir: Path | None = None) -> "EnvironmentRegistry":
        """
        Get the singleton instance of the registry.

        Args:
            environments_dir: Path to environments directory (required on first call)

        Returns:
            The singleton registry instance
        """
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    if environments_dir is None:
                        raise ValueError("environments_dir is required on first call")
                    cls._instance = cls(environments_dir)
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset the singleton instance (for testing)."""
        with cls._lock:
            cls._instance = None

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

    def register(self, env_config: "EnvironmentConfig") -> EnvironmentEntry:
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

    def list_all(self) -> list[EnvironmentEntry]:
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

    def reload(self) -> None:
        """Force reload data from disk."""
        with self._file_lock:
            self._data = self._load()


class EnvironmentPathResolver:
    """
    Resolves environment paths using the registry.

    Combines PathsConfig with EnvironmentRegistry to resolve
    environment paths based on env_id -> name lookup.
    """

    def __init__(self, environments_dir: Path, registry: EnvironmentRegistry) -> None:
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


# Global instances (initialized lazily)
_registry: EnvironmentRegistry | None = None
_path_resolver: EnvironmentPathResolver | None = None


def get_registry() -> EnvironmentRegistry:
    """Get the global registry instance."""
    global _registry
    if _registry is None:
        from leropilot.services.config import get_config

        config = get_config()
        assert config.paths.environments_dir is not None
        _registry = EnvironmentRegistry(config.paths.environments_dir)
    return _registry


def get_path_resolver() -> EnvironmentPathResolver:
    """Get the global path resolver instance."""
    global _path_resolver
    if _path_resolver is None:
        from leropilot.services.config import get_config

        config = get_config()
        assert config.paths.environments_dir is not None
        _path_resolver = EnvironmentPathResolver(config.paths.environments_dir, get_registry())
    return _path_resolver
