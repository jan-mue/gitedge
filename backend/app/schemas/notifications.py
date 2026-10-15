"""Notification center and delivery preference contracts."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import Field

from app.entities.activity import ActivityKind
from app.schemas.base import GitEdgeBaseModel

NotificationCategory = Literal["issue", "pull", "mention", "release", "repository"]
NOTIFICATION_CATEGORIES: tuple[NotificationCategory, ...] = ("issue", "pull", "mention", "release", "repository")


class NotificationPublic(GitEdgeBaseModel):
    """An inbox entry and its destination."""

    id: uuid.UUID
    repo_id: uuid.UUID
    repo: str
    number: int | None
    title: str
    kind: ActivityKind
    category: NotificationCategory
    reason: str
    actor: str
    url: str
    created_at: datetime
    is_read: bool
    is_archived: bool
    unsubscribed: bool


class NotificationsPublic(GitEdgeBaseModel):
    """A filtered notification page with inbox navigation counts."""

    data: list[NotificationPublic]
    count: int
    inbox_count: int
    archived_count: int
    repository_counts: dict[str, int]
    unread_count: int
    repositories: list[str]
    reasons: dict[str, int]


class NotificationUpdate(GitEdgeBaseModel):
    """Apply explicit states to selected notifications, never to another user's inbox."""

    ids: list[uuid.UUID] = Field(min_length=1, max_length=100)
    is_read: bool | None = None
    is_archived: bool | None = None
    unsubscribed: bool | None = None


class NotificationPreferences(GitEdgeBaseModel):
    """Email is opt-in; every delivered event also remains in the center."""

    email: bool = False


class NotificationPreferencesPublic(NotificationPreferences):
    """Saved preference and installation delivery capability."""

    email_available: bool


class RepositoryNotificationPreferences(GitEdgeBaseModel):
    """Allowed categories for future events from a repository."""

    categories: list[NotificationCategory] = Field(default_factory=lambda: list(NOTIFICATION_CATEGORIES))


class NotificationFilter(GitEdgeBaseModel):
    """Validated inbox filters shared by persistence and service layers."""

    view: Literal["inbox", "archived"] = "inbox"
    read: Literal["all", "unread"] = "all"
    reason: str = ""
    repo: str = ""
    query: str = ""
    offset: int = 0
    limit: int = 50
    focus: uuid.UUID | None = None
