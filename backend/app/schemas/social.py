"""Social schemas: stars, watchers and forks."""

import uuid
from datetime import datetime

from app.schemas.base import GitEdgeBaseModel
from app.schemas.users import UserPublic


class StarState(GitEdgeBaseModel):
    """Whether the current user starred a repository, and the total count."""

    is_starred: bool
    stars_count: int


class WatcherState(GitEdgeBaseModel):
    """Whether the current user watches a repository, and the total count."""

    is_watching: bool
    watchers_count: int


class StargazersPublic(GitEdgeBaseModel):
    """List of users who starred a repository."""

    data: list[UserPublic]
    count: int


class WatchersPublic(GitEdgeBaseModel):
    """List of users watching a repository."""

    data: list[UserPublic]
    count: int


class ForkCreate(GitEdgeBaseModel):
    """Request to fork a repository."""

    owner: str | None = None
    name: str | None = None
    description: str | None = None


class ForkPublic(GitEdgeBaseModel):
    """Public representation of a fork."""

    id: uuid.UUID
    path: str
    name: str
    owner: str | None = None
    description: str | None = None
    stars_count: int = 0
    forks_count: int = 0
    created_at: datetime | None = None


class ForksPublic(GitEdgeBaseModel):
    """List of forks for a repository."""

    data: list[ForkPublic]
    count: int
