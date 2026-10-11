"""Activity feed schemas."""

import uuid
from datetime import datetime

from app.entities.activity import ActivityKind, ActivityTargetType
from app.entities.issues import IssueState
from app.schemas.base import GitEdgeBaseModel


class ActivityTargetPreview(GitEdgeBaseModel):
    """Current issue or pull request details, with the description limited to 4,000 characters."""

    body: str | None = None
    body_truncated: bool = False
    state: IssueState
    comments_count: int


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
    preview: ActivityTargetPreview | None = None


class ActivitiesPublic(GitEdgeBaseModel):
    """List of activity events."""

    data: list[ActivityPublic]
    count: int
