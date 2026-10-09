"""Activity entity model for the feed."""

import uuid
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import UUID, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.entities.base import Base

if TYPE_CHECKING:
    from app.entities.repositories import Repository
    from app.entities.users import User


class ActivityKind(StrEnum):
    """Kinds of activity recorded in the feed."""

    STAR = "star"
    WATCH = "watch"
    FORK = "fork"
    ISSUE_OPEN = "issue_open"
    ISSUE_CLOSE = "issue_close"
    ISSUE_REOPEN = "issue_reopen"
    COMMENT = "comment"
    PULL_REQUEST_OPEN = "pull_request_open"
    PULL_REQUEST_MERGE = "pull_request_merge"
    PULL_REQUEST_CLOSE = "pull_request_close"
    PULL_REQUEST_REOPEN = "pull_request_reopen"
    RELEASE = "release"


class ActivityTargetType(StrEnum):
    """Types of targets an activity event can reference."""

    REPOSITORY = "repository"
    ISSUE = "issue"
    PULL_REQUEST = "pull_request"
    RELEASE = "release"


class Activity(Base):
    """A recorded activity event shown in user and repository feeds."""

    __tablename__ = "activity"

    actor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("user.id"), nullable=False, index=True)
    repo_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("repository.id"), nullable=True, index=True
    )
    kind: Mapped[ActivityKind] = mapped_column(String(40), nullable=False)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    target_type: Mapped[ActivityTargetType | None] = mapped_column(String(40), nullable=True)
    target_number: Mapped[int | None] = mapped_column(Integer, nullable=True)

    actor: Mapped["User"] = relationship(back_populates="activities")
    repo: Mapped["Repository | None"] = relationship(back_populates="activities")
