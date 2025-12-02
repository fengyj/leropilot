"""Installation configuration models."""

from pydantic import BaseModel


class EnvironmentInstallStepTemplate(BaseModel):
    """Template for an installation step."""

    id: str
    commands: list[str]  # Array of command templates with variable placeholders
    cwd: str | None = None  # Working directory (optional, uses default if not specified)
    env_vars: dict[str, str] = {}  # Step-specific environment variables


class CompatibilityEntry(BaseModel):
    """Entry in the compatibility matrix."""

    torch: str
    cuda: list[str] = []
    rocm: list[str] = []
    cpu: bool = False
    torchvision: str | None = None
    torchaudio: str | None = None
    is_recommended: bool = False


class VersionConfig(BaseModel):
    """Configuration for a specific version/ref."""

    python_version: str
    torch_version: str
    compatibility_matrix: list[CompatibilityEntry] = []
    # Platform-specific steps
    darwin: list[EnvironmentInstallStepTemplate] = []
    linux: list[EnvironmentInstallStepTemplate] = []
    windows: list[EnvironmentInstallStepTemplate] = []


class RepoConfig(BaseModel):
    """Configuration for a repository."""

    versions: dict[str, VersionConfig] = {}


class EnvironmentInstallationConfig(BaseModel):
    """
    Root configuration loaded from environment_installation_config.json.
    Centralizes all installation logic, dependencies, and step definitions.
    """

    repositories: dict[str, RepoConfig]
