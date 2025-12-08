"""Environment data models for LeRoPilot."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class EnvironmentConfig(BaseModel):
    """Configuration for a specific LeRobot environment."""

    id: str
    name: str
    display_name: str
    created_at: datetime = Field(default_factory=datetime.now)

    # Source
    repo_id: str
    repo_url: str
    ref: str  # tag, branch, or commit
    commit_hash: str | None = None

    # Python
    python_version: str

    # Hardware
    torch_version: str
    torchvision_version: str | None = None
    torchaudio_version: str | None = None
    cuda_version: str | None = None
    rocm_version: str | None = None

    # Extras
    extras: list[str] = Field(default_factory=list)

    # Status
    status: Literal["pending", "installing", "ready", "error"] = "pending"
    error_message: str | None = None


class EnvironmentInstallStep(BaseModel):
    """Represents a single installation step."""

    id: str
    name: str
    comment: str | None = None
    commands: list[str]
    cwd: str | None = None  # Working directory for the commands
    env_vars: dict[str, str] = Field(default_factory=dict)  # Step-specific environment variables
    status: Literal["pending", "running", "success", "error"] = "pending"
    logs: list[str] = Field(default_factory=list)
    start_time: datetime | None = None
    end_time: datetime | None = None
    exit_code: int | None = None


class EnvironmentInstallationPlan(BaseModel):
    """Complete installation plan with all required information."""

    # Environment paths
    env_dir: str  # Environment directory
    repo_dir: str  # Repository directory
    venv_path: str  # Virtual environment path
    log_file: str  # Installation log file

    # Installation steps with resolved commands
    steps: list[EnvironmentInstallStep]

    # Environment variables for installation
    env_vars: dict[str, str] = Field(default_factory=dict)

    # Default working directory (if not specified in step)
    default_cwd: str


class EnvironmentInstallation(BaseModel):
    """Represents an ongoing or completed installation."""

    id: str
    env_config: EnvironmentConfig
    plan: EnvironmentInstallationPlan  # Complete installation plan
    status: Literal["pending", "running", "success", "error", "cancelled"] = "pending"
    session_id: str | None = None  # PTY session ID for resuming installations
    created_at: datetime = Field(default_factory=datetime.now)
    completed_at: datetime | None = None
