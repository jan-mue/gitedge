"""Release and tag schemas."""

import uuid
from datetime import datetime

from app.schemas.base import GitEdgeBaseModel


class ReleaseCreate(GitEdgeBaseModel):
    """Request to create a release."""

    tag_name: str
    name: str | None = None
    body: str | None = None
    target_commitish: str = "main"
    is_draft: bool = False
    is_prerelease: bool = False


class ReleasePublic(GitEdgeBaseModel):
    """Public release representation."""

    id: uuid.UUID
    repo_path: str
    tag_name: str
    name: str | None = None
    body: str | None = None
    target_commitish: str = "main"
    is_draft: bool = False
    is_prerelease: bool = False
    author_email: str | None = None
    author_username: str | None = None
    published_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ReleasesPublic(GitEdgeBaseModel):
    """List of releases."""

    data: list[ReleasePublic]
    count: int


class TagInfo(GitEdgeBaseModel):
    """Information about a Git tag."""

    name: str
    commit_sha: str
    timestamp: int | None = None


class TagsPublic(GitEdgeBaseModel):
    """List of Git tags."""

    data: list[TagInfo]
    count: int
