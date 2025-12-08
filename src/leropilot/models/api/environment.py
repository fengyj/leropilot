"""API response models for environment operations."""

from datetime import datetime

from pydantic import BaseModel

from leropilot.models.environment import EnvironmentConfig, EnvironmentInstallationPlan, EnvironmentInstallStep


class CreateEnvironmentRequest(BaseModel):
    """Request to create an environment."""

    env_config: EnvironmentConfig
    custom_steps: list[EnvironmentInstallStep] | None = None


class ExecuteRequest(BaseModel):
    """Request to execute a command."""

    step_id: str
    command_index: int
    exit_code: int | None = None
    execution_id: str | None = None


class ExtraInfo(BaseModel):
    """Extra information for environment."""

    id: str
    name: str
    description: str
    category: str = "other"
    category_label: str = ""
    selected: bool = False


class GenerateStepsRequest(BaseModel):
    """Request to generate installation steps."""

    env_config: EnvironmentConfig


class GenerateStepsResponse(BaseModel):
    """Response for step generation."""

    steps: list[EnvironmentInstallStep]


class HardwareInfo(BaseModel):
    """Hardware detection information."""

    detected_cuda: str | None
    detected_rocm: str | None
    detected_driver: str | None
    detected_gpu: str | None
    has_nvidia_gpu: bool
    has_amd_gpu: bool
    is_apple_silicon: bool


class HasEnvironmentsResponse(BaseModel):
    """Response for check_has_environments."""

    has_environments: bool


class CreateEnvironmentResponse(BaseModel):
    """Response for environment creation."""

    installation_id: str
    env_id: str
    status: str
    steps: list[EnvironmentInstallStep]
    message: str


class InstallationStatusResponse(BaseModel):
    """Response for installation status."""

    installation_id: str
    env_id: str
    status: str
    progress: int
    steps: list[EnvironmentInstallStep]
    created_at: datetime
    completed_at: datetime | None = None


class StartInstallationResponse(BaseModel):
    """Response for starting installation."""

    session_id: str
    plan: EnvironmentInstallationPlan
    env_name: str  # Display name of the environment
    is_windows: bool


class NextStepInfo(BaseModel):
    """Information about the next step to execute."""

    step_id: str
    step_index: int
    total_steps: int
    command_index: int
    command: str
    name: str


class ExecuteInstallationResponse(BaseModel):
    """Response for executing an installation step."""

    status: str
    step_id: str | None = None
    command_index: int | None = None
    error: str | None = None
    next_step: NextStepInfo | None = None


class CancelInstallationResponse(BaseModel):
    """Response for cancelling installation."""

    success: bool
    message: str


class DeleteEnvironmentResponse(BaseModel):
    """Response for deleting environment."""

    success: bool
    message: str


class OpenTerminalResponse(BaseModel):
    """Response for opening terminal."""

    success: bool
    message: str
