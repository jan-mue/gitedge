"""Activity feed schemas."""

import uuid
from datetime import datetime

from app.schemas.base import GitEdgeBaseModel


class ActivityPublic(GitEdgeBaseModel):
    """Public activity representation."""

    id: uuid.UUID
    kind: str
    title: str | None = None
    actor_email: str | None = None
    actor_username: str | None = None
    repo_path: str | None = None
    target_type: str | None = None
    target_number: int | None = None
    created_at: datetime | None = None


class ActivitiesPublic(GitEdgeBaseModel):
    """List of activity events."""

    data: list[ActivityPublic]
    count: int
