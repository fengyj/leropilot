"""Configuration management for LeRoPilot."""

import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any, Literal, cast

import yaml

from leropilot.models.app_config import AppConfig, PyPIMirror, RepositorySource


def _get_resources_dir() -> Path:
    """Get the resources directory path, compatible with PyInstaller."""
    if getattr(sys, "frozen", False):
        # PyInstaller packaged environment
        base_path = Path(sys._MEIPASS)  # type: ignore[attr-defined]
        return base_path / "leropilot" / "resources"
    else:
        # Development environment
        return Path(__file__).parent.parent / "resources"


class AppConfigManager:
    """Manages application configuration with YAML file and environment variable support."""

    def __init__(self, config_path: Path | None = None) -> None:
        """Initialize configuration manager.

        Args:
            config_path: Path to config file. If None, uses LEROPILOT_CONFIG_PATH
                        environment variable or defaults to platform-specific config directory
        """
        if config_path is None:
            # Check environment variable first
            env_path = os.getenv("LEROPILOT_CONFIG_PATH")
            if env_path:
                config_path = Path(env_path).expanduser()
            else:
                # Use platform-specific config directory
                import sys

                if sys.platform == "win32":
                    # Windows: %APPDATA%\LeRoPilot
                    config_dir = Path(os.getenv("APPDATA", str(Path.home()))) / "LeRoPilot"
                elif sys.platform == "darwin":
                    # macOS: ~/Library/Application Support/LeRoPilot
                    config_dir = Path.home() / "Library" / "Application Support" / "LeRoPilot"
                else:
                    # Linux/Unix: ~/.config/leropilot
                    config_dir = Path.home() / ".config" / "leropilot"

                config_path = config_dir / "config.yaml"

        self.config_path = config_path
        self._config: AppConfig | None = None

    def load(self) -> AppConfig:
        """Load configuration from file and apply environment variable overrides.

        Returns:
            Loaded configuration
        """
        config_data: dict[str, Any] = {}
        is_first_time = not self.config_path.exists()

        # Debug output for troubleshooting (always visible via print)
        print(f"[CONFIG] Loading config from: {self.config_path}")
        print(f"[CONFIG] Config file exists: {self.config_path.exists()}")
        print(f"[CONFIG] Is first time user: {is_first_time}")

        # 1. Load from YAML file if it exists
        if self.config_path.exists():
            with open(self.config_path, encoding="utf-8") as f:
                config_data = yaml.safe_load(f) or {}

        # 2. Create config object (applies defaults)
        config = AppConfig(**config_data)

        # 3. Load preset configuration for first-time users
        if is_first_time:
            print("[CONFIG] First time user detected, applying preset configuration...")
            config = self._apply_preset_config(config)
            # Save the preset config so it persists
            print(f"[CONFIG] Saving preset config to: {self.config_path}")
            self.save(config)
            print("[CONFIG] Preset config saved successfully")
        else:
            print(
                f"[CONFIG] Existing config loaded with {len(config.repositories.lerobot_sources)} repos "
                f"and {len(config.pypi.mirrors)} mirrors"
            )

        # 4. Apply environment variable overrides
        config = self._apply_env_overrides(config)

        return config

    def save(self, config: AppConfig) -> None:
        """Save configuration to YAML file.

        Args:
            config: Configuration to save
        """
        self.config_path.parent.mkdir(parents=True, exist_ok=True)

        # Convert to dict, converting Path objects to strings
        config_dict = self._config_to_dict(config)

        with open(self.config_path, "w", encoding="utf-8") as f:
            yaml.dump(config_dict, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

    def _config_to_dict(self, config: AppConfig) -> dict[str, Any]:
        """Convert config to dictionary with Path objects as strings.

        Args:
            config: Configuration object

        Returns:
            Dictionary representation
        """
        config_dict = config.model_dump(mode="json", exclude_none=True)

        # Convert Path objects to strings for YAML serialization
        def convert_paths(obj: Any) -> Any:  # noqa: ANN401
            if isinstance(obj, dict):
                return {k: convert_paths(v) for k, v in obj.items()}
            if isinstance(obj, list):
                return [convert_paths(item) for item in obj]
            if isinstance(obj, Path):
                return str(obj)
            return obj

        return cast(dict[str, Any], convert_paths(config_dict))

    def _apply_preset_config(self, config: AppConfig) -> AppConfig:
        """Apply preset configuration for first-time users.

        Loads preset PyPI mirrors and repositories from default_config.json,
        and detects system language for UI settings.

        Args:
            config: Base configuration

        Returns:
            Configuration with presets applied
        """
        # Detect and apply system language
        detected_lang = self._detect_system_language()
        if detected_lang:
            config.ui.preferred_language = detected_lang
            print(f"[CONFIG] Detected system language: {detected_lang}")

        try:
            # Load preset configuration file
            resources_dir = _get_resources_dir()
            preset_path = resources_dir / "default_config.json"
            print(f"[CONFIG] Loading preset config from: {preset_path}")
            print(f"[CONFIG] Resources dir exists: {resources_dir.exists()}")
            print(f"[CONFIG] Preset file exists: {preset_path.exists()}")

            if not preset_path.exists():
                print(f"[CONFIG] WARNING: Preset config file not found at: {preset_path}")
                return config

            with open(preset_path, encoding="utf-8") as f:
                preset_data = json.load(f)

            print(f"[CONFIG] Loaded preset data keys: {list(preset_data.keys())}")

            # Apply preset PyPI mirrors (only if user has no mirrors configured)
            if not config.pypi.mirrors and "pypi_mirrors" in preset_data:
                config.pypi.mirrors = [
                    PyPIMirror(
                        name=m["name"],
                        url=m["url"],
                        enabled=m.get("enabled", False),
                    )
                    for m in preset_data["pypi_mirrors"]
                ]
                print(f"[CONFIG] Applied {len(config.pypi.mirrors)} preset PyPI mirrors")

            if not config.repositories.lerobot_sources and "repositories" in preset_data:
                config.repositories.lerobot_sources = [
                    RepositorySource(
                        id=r["id"],
                        name=r["name"],
                        url=r["url"],
                        is_default=r.get("is_default", False),
                    )
                    for r in preset_data["repositories"]["lerobot_sources"]
                ]
                print(f"[CONFIG] Applied {len(config.repositories.lerobot_sources)} preset repositories")

        except Exception as e:
            # Log error but don't fail configuration loading
            print(f"[CONFIG] ERROR: Failed to load preset configuration: {e}")
            import traceback

            traceback.print_exc()

        return config

    def _detect_system_language(self) -> Literal["en", "zh"]:
        """Detect the system language and return a supported language code.

        Checks system locale settings to determine the user's preferred language.
        Falls back to English if the detected language is not supported.

        Returns:
            Language code: 'zh' for Chinese, 'en' for English (default)
        """
        import locale

        default_language: Literal["en", "zh"] = "en"

        try:
            # Try to get system locale
            # This works on Windows, macOS, and Linux
            system_locale = locale.getdefaultlocale()[0]  # e.g., 'en_US', 'zh_CN', 'zh_TW'

            if system_locale:
                # Extract language code (first 2 characters)
                lang_code = system_locale[:2].lower()
                print(f"[CONFIG] System locale detected: {system_locale} -> {lang_code}")

                if lang_code == "zh":
                    return "zh"
                if lang_code == "en":
                    return "en"

            # Fallback: Check environment variables directly
            for env_var in ["LANG", "LANGUAGE", "LC_ALL", "LC_MESSAGES"]:
                env_value = os.getenv(env_var, "")
                if env_value:
                    lang_code = env_value[:2].lower()
                    print(f"[CONFIG] Language from {env_var}: {env_value} -> {lang_code}")
                    if lang_code == "zh":
                        return "zh"
                    if lang_code == "en":
                        return "en"

        except Exception as e:
            print(f"[CONFIG] Failed to detect system language: {e}")

        print(f"[CONFIG] Using default language: {default_language}")
        return default_language

    def _apply_env_overrides(self, config: AppConfig) -> AppConfig:
        """Apply environment variable overrides.

        Environment variables use the format: LEROPILOT_<SECTION>_<KEY>
        Examples:
            - LEROPILOT_SERVER_PORT=9000
            - LEROPILOT_DATA_DIR=~/custom/path

        Args:
            config: Base configuration

        Returns:
            Configuration with environment overrides applied
        """
        # Server overrides
        if port := os.getenv("LEROPILOT_SERVER_PORT"):
            config.server.port = int(port)
        if host := os.getenv("LEROPILOT_SERVER_HOST"):
            config.server.host = host
        if auto_open := os.getenv("LEROPILOT_SERVER_AUTO_OPEN_BROWSER"):
            config.server.auto_open_browser = auto_open.lower() in ("true", "1", "yes")

        # UI overrides
        if theme := os.getenv("LEROPILOT_UI_THEME"):
            if theme in ("system", "light", "dark"):
                config.ui.theme = theme  # type: ignore
        if lang := os.getenv("LEROPILOT_UI_PREFERRED_LANGUAGE"):
            if lang in ("en", "zh"):
                config.ui.preferred_language = lang  # type: ignore

        # Path overrides
        if data_dir := os.getenv("LEROPILOT_DATA_DIR"):
            config.paths.data_dir = Path(data_dir).expanduser()
            # Recalculate dependent paths
            config.paths.model_post_init(None)

        # PyPI overrides
        if index_url := os.getenv("LEROPILOT_PYPI_INDEX_URL"):
            # Add or update environment override mirror
            from leropilot.models.app_config import PyPIMirror

            # Remove existing env override if any
            config.pypi.mirrors = [m for m in config.pypi.mirrors if m.name != "Env Override"]

            # Add new mirror at the beginning
            config.pypi.mirrors.insert(0, PyPIMirror(name="Env Override", url=index_url, enabled=True))

            # Ensure only one is enabled
            for m in config.pypi.mirrors[1:]:
                m.enabled = False

        # HuggingFace overrides
        if hf_token := os.getenv("LEROPILOT_HF_TOKEN"):
            config.huggingface.token = hf_token

        # Advanced overrides
        if log_level := os.getenv("LEROPILOT_ADVANCED_LOG_LEVEL"):
            if log_level in ("INFO", "DEBUG", "TRACE"):
                config.advanced.log_level = log_level  # type: ignore
        if log_max_size := os.getenv("LEROPILOT_ADVANCED_LOG_MAX_SIZE_MB"):
            try:
                config.advanced.log_max_size_mb = int(log_max_size)
            except ValueError:
                pass  # Keep default if invalid
        if log_backup_count := os.getenv("LEROPILOT_ADVANCED_LOG_BACKUP_COUNT"):
            try:
                config.advanced.log_backup_count = int(log_backup_count)
            except ValueError:
                pass  # Keep default if invalid

        return config

    def get_config(self) -> AppConfig:
        """Get configuration (singleton pattern).

        Returns:
            Current configuration
        """
        if self._config is None:
            self._config = self.load()
        return self._config

    def reload(self) -> AppConfig:
        """Reload configuration from file.

        Returns:
            Reloaded configuration
        """
        self._config = self.load()
        return self._config


# Global configuration manager instance
_config_manager = AppConfigManager()


def get_config() -> AppConfig:
    """Get global application configuration.

    Returns:
        Application configuration
    """
    return _config_manager.get_config()


def reload_config() -> AppConfig:
    """Reload configuration from file.

    Returns:
        Reloaded configuration
    """
    return _config_manager.reload()


def save_config(config: AppConfig) -> None:
    """Save configuration to file.

    Args:
        config: Configuration to save
    """
    _config_manager.save(config)


# Configuration business logic functions


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


async def update_config_business_logic(new_config: AppConfig) -> AppConfig:
    """Update configuration with business logic validation and data migration.

    Args:
        new_config: New configuration to apply

    Returns:
        Updated and reloaded configuration

    Raises:
        ValueError: If update fails due to business logic constraints
    """
    # Get current config to check if data_dir is being changed
    current_config = get_config()

    # Check for removed repositories and clean up their directories
    current_repo_ids = {repo.id for repo in current_config.repositories.lerobot_sources}
    new_repo_ids = {repo.id for repo in new_config.repositories.lerobot_sources}
    removed_repo_ids = current_repo_ids - new_repo_ids

    for repo_id in removed_repo_ids:
        repo_path = current_config.paths.get_repo_path(repo_id)
        if repo_path.exists():
            try:
                shutil.rmtree(repo_path)
                from leropilot.logger import get_logger

                logger = get_logger(__name__)
                logger.info(f"Removed repository directory: {repo_path}")
            except Exception as e:
                from leropilot.logger import get_logger

                logger = get_logger(__name__)
                logger.warning(f"Failed to remove repository directory {repo_path}: {e}")

    # Check if data_dir is being changed
    if current_config.paths.data_dir != new_config.paths.data_dir:
        # Check if environments exist
        has_envs = await check_has_environments()
        if has_envs:
            raise ValueError(
                "Cannot change data directory after environments have been created. "
                "This is to prevent data loss and ensure data integrity."
            )

        # Migrate existing data
        try:
            await migrate_data_directory(current_config.paths.data_dir, new_config.paths.data_dir)
        except Exception as e:
            raise ValueError(f"Failed to migrate data: {str(e)}") from e

    save_config(new_config)
    return reload_config()


async def reset_config_business_logic() -> AppConfig:
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
