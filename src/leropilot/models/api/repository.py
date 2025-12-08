"""API models for repository operations."""

from pydantic import BaseModel


class RepositoryInfo(BaseModel):
    """Repository information."""

    id: str
    name: str
    url: str
    is_default: bool = False


class VersionCompatibilityEntry(BaseModel):
    """Compatibility entry for API response."""

    torch: str
    cuda: list[str] = []
    rocm: list[str] = []
    cpu: bool = False
    torchvision: str | None = None
    torchaudio: str | None = None
    is_recommended: bool = False


class VersionInfo(BaseModel):
    """Version information."""

    tag: str
    is_stable: bool
    python_version: str | None = None
    torch_version: str | None = None
    compatibility_matrix: list[VersionCompatibilityEntry] = []


class RepositoryStatus(BaseModel):
    """Repository download status."""

    repo_id: str
    is_downloaded: bool
    last_updated: str | None = None
    cache_path: str | None = None
