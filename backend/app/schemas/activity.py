"""Activity feed schemas."""

import uuid
from datetime import datetime

from app.entities.activity import ActivityKind, ActivityTargetType
from app.schemas.base import GitEdgeBaseModel


class ActivityPublic(GitEdgeBaseModel):
    """Public activity representation."""

    id: uuid.UUID
    kind: ActivityKind
    title: str | None = None
    actor_username: str
    repo_owner: str | None = None
    repo_name: str | None = None
    target_type: ActivityTargetType | None = None
    target_number: int | None = None
    created_at: datetime


class ActivitiesPublic(GitEdgeBaseModel):
    """List of activity events."""

    data: list[ActivityPublic]
    count: int
