"""Configuration data models for LeRoPilot."""

import sys
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from leropilot.models.repository import RepositorySource


class ServerConfig(BaseModel):
    """Server configuration."""

    # IMPORTANT: Default port - must match Electron configuration
    # Corresponding file: electron/main.js -> DEFAULT_PORT
    # If modified, update both locations
    port: int = 8000
    host: str = "127.0.0.1"
    auto_open_browser: bool = True


class UIConfig(BaseModel):
    """UI configuration."""

    theme: Literal["system", "light", "dark"] = "system"
    preferred_language: Literal["en", "zh"] = "en"


class PathsConfig(BaseModel):
    """Paths configuration."""

    data_dir: Path = Field(default_factory=lambda: Path.home() / ".leropilot")
    repos_dir: Path | None = None
    environments_dir: Path | None = None
    logs_dir: Path | None = None
    cache_dir: Path | None = None
    uv_cache_dir: Path | None = None  # cache folder for uv. Set the value to env var: UV_CACHE_DIR
    tools_cache_dir: Path | None = None  # Cache for downloaded tools like FFmpeg, etc.
    tools_dir: Path | None = None  # Directory for bundled tools like  Git portable, etc.

    @field_validator("data_dir", mode="before")
    @classmethod
    def expand_data_dir(cls, v: str | Path) -> Path:
        """Expand user path for data_dir."""
        if isinstance(v, str):
            return Path(v).expanduser()
        return v

    @field_validator("repos_dir", "environments_dir", "logs_dir", "cache_dir", "tools_dir", mode="before")
    @classmethod
    def expand_optional_path(cls, v: str | Path | None) -> Path | None:
        """Expand user path for optional paths."""
        if v is None:
            return None
        if isinstance(v, str):
            return Path(v).expanduser()
        return v

    def model_post_init(self, __context: object) -> None:
        """Set default subdirectories if not specified."""
        if self.repos_dir is None:
            self.repos_dir = self.data_dir / "repos"
        if self.environments_dir is None:
            self.environments_dir = self.data_dir / "environments"
        if self.logs_dir is None:
            self.logs_dir = self.data_dir / "logs"
        if self.cache_dir is None:
            self.cache_dir = self.data_dir / "cache"
        if self.uv_cache_dir is None:
            self.uv_cache_dir = self.cache_dir / "uv_cache"
        if self.tools_cache_dir is None:
            self.tools_cache_dir = self.cache_dir / "tools"
        if self.tools_dir is None:
            self.tools_dir = self.data_dir / "tools"

    # Helper methods for standardized subdirectory access

    def get_repo_path(self, repo_id: str) -> Path:
        """
        Get cache path for a repository.

        This directory stores cloned Git repositories that are shared across all environments.
        Each repository is cloned once and reused by multiple environments, saving disk space
        and download time.

        Directory structure:
            repos/{repo_id}/.git/          - Git repository metadata
            repos/{repo_id}/pyproject.toml - Project configuration
            repos/{repo_id}/src/           - Source code
            repos/{repo_id}/...            - Other repository files

        Example paths:
            - repos/official/              - Official HuggingFace LeRobot repository
            - repos/custom/                - Custom fork or alternative repository

        Args:
            repo_id: Repository identifier (e.g., "official", "custom")

        Returns:
            Path to repository cache directory (e.g., ~/.leropilot/repos/official)
        """
        assert self.repos_dir is not None
        return self.repos_dir / repo_id

    def get_tools_cache_path(self) -> Path:
        """
        Get cache path for tools (bundled dependencies).

        This directory stores downloaded binary tools and dependencies that are shared
        across all environments, such as:

        - FFmpeg binaries (for video processing)
        - Git portable (bundled Git for systems without system Git)
        - Other system-level tools

        Directory structure:
            cache/tools/ffmpeg-7.1.3/bin/ffmpeg   - FFmpeg binary
            cache/tools/ffmpeg-7.1.3/bin/ffprobe  - FFprobe binary
            cache/tools/...                       - Other tools

        Example usage:
            During environment installation, FFmpeg binaries are copied from
            cache/tools/ffmpeg-{version}/ to the environment's bin/ directory.

        Note: This is different from environment-specific tools, which are stored
        in each environment's directory.

        Returns:
            Path to tools cache directory (e.g., ~/.leropilot/cache/tools)
        """
        assert self.tools_cache_dir is not None
        return self.tools_cache_dir


class ToolSource(BaseModel):
    """Tool source configuration."""

    type: Literal["bundled", "custom"] = "bundled"
    custom_path: str = ""


class ToolsConfig(BaseModel):
    """Tools configuration."""

    git: ToolSource = Field(default_factory=ToolSource)


class RepositoriesConfig(BaseModel):
    """Repositories configuration."""

    lerobot_sources: list[RepositorySource] = []


class PyPIMirror(BaseModel):
    """PyPI mirror configuration."""

    name: str
    url: str
    enabled: bool = False  # Only one mirror can be enabled at a time


class PyPIConfig(BaseModel):
    """PyPI configuration."""

    mirrors: list[PyPIMirror] = Field(default_factory=list)


class HuggingFaceConfig(BaseModel):
    """HuggingFace configuration."""

    token: str = ""
    cache_dir: Path = Field(default_factory=lambda: Path.home() / ".cache" / "huggingface")

    @field_validator("cache_dir", mode="before")
    @classmethod
    def expand_cache_dir(cls, v: str | Path) -> Path:
        """Expand user path for cache_dir."""
        if isinstance(v, str):
            return Path(v).expanduser()
        return v


class AdvancedConfig(BaseModel):
    """Advanced configuration."""

    installation_timeout: int = 3600  # Timeout in seconds to prevent hung installations
    log_level: Literal["INFO", "DEBUG", "TRACE"] = "INFO"
    log_max_size_mb: int = 10  # Maximum log file size in MB before rotation
    log_backup_count: int = 5  # Number of backup log files to keep


class AppConfig(BaseModel):
    """Application configuration."""

    server: ServerConfig = Field(default_factory=ServerConfig)
    ui: UIConfig = Field(default_factory=UIConfig)
    paths: PathsConfig = Field(default_factory=PathsConfig)
    tools: ToolsConfig = Field(default_factory=ToolsConfig)
    repositories: RepositoriesConfig = Field(default_factory=RepositoriesConfig)
    pypi: PyPIConfig = Field(default_factory=PyPIConfig)
    huggingface: HuggingFaceConfig = Field(default_factory=HuggingFaceConfig)
    advanced: AdvancedConfig = Field(default_factory=AdvancedConfig)
