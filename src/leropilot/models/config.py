"""Configuration data models for LeRoPilot."""

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, field_validator


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

    @field_validator("data_dir", mode="before")
    @classmethod
    def expand_data_dir(cls, v: str | Path) -> Path:
        """Expand user path for data_dir."""
        if isinstance(v, str):
            return Path(v).expanduser()
        return v

    @field_validator("repos_dir", "environments_dir", "logs_dir", "cache_dir", mode="before")
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


class ToolSource(BaseModel):
    """Tool source configuration."""

    type: Literal["bundled", "custom"] = "bundled"
    custom_path: str = ""


class ToolsConfig(BaseModel):
    """Tools configuration."""

    git: ToolSource = Field(default_factory=ToolSource)
    uv: ToolSource = Field(default_factory=ToolSource)


class RepositorySource(BaseModel):
    """Repository source configuration."""

    name: str
    url: str
    is_default: bool = False


class RepositoriesConfig(BaseModel):
    """Repositories configuration."""

    lerobot_sources: list[RepositorySource] = Field(
        default_factory=lambda: [
            RepositorySource(
                name="Official",
                url="https://github.com/huggingface/lerobot.git",
                is_default=True,
            )
        ]
    )
    default_branch: str = "main"
    default_version: str = "v2.0"


class PyPIMirror(BaseModel):
    """PyPI mirror configuration."""

    name: str
    url: str
    is_default: bool = False


class PyPIConfig(BaseModel):
    """PyPI configuration."""

    mirrors: list[PyPIMirror] = Field(
        default_factory=lambda: [PyPIMirror(name="Official PyPI", url="https://pypi.org/simple", is_default=True)]
    )


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
