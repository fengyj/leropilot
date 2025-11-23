"""Configuration management for LeRoPilot."""

import os
from pathlib import Path
from typing import Any

import yaml

from leropilot.models.config import AppConfig


class ConfigManager:
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

        # 1. Load from YAML file if it exists
        if self.config_path.exists():
            with open(self.config_path) as f:
                config_data = yaml.safe_load(f) or {}

        # 2. Create config object (applies defaults)
        config = AppConfig(**config_data)

        # 3. Apply environment variable overrides
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

        with open(self.config_path, "w") as f:
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

        return convert_paths(config_dict)

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
            from leropilot.models.config import PyPIMirror

            # Remove existing env override if any
            config.pypi.mirrors = [m for m in config.pypi.mirrors if m.name != "Env Override"]

            # Add new mirror at the beginning
            config.pypi.mirrors.insert(0, PyPIMirror(name="Env Override", url=index_url, is_default=True))

            # Ensure only one default
            for m in config.pypi.mirrors[1:]:
                m.is_default = False

        # HuggingFace overrides
        if hf_token := os.getenv("LEROPILOT_HF_TOKEN"):
            config.huggingface.token = hf_token

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
_config_manager = ConfigManager()


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
