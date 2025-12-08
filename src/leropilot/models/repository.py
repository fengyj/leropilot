"""Repository related models."""

from pydantic import BaseModel


class RepositoryStatus(BaseModel):
    """Repository download/cache status."""

    repo_id: str
    is_downloaded: bool
    last_updated: str | None = None
    cache_path: str | None = None


class RepositorySource(BaseModel):
    """Repository source configuration."""

    id: str
    name: str
    url: str
    is_default: bool = False
