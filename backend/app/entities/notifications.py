"""Persistent notification inbox, delivery preferences, and thread subscriptions."""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import JSON, UUID, Boolean, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.entities.base import Base

if TYPE_CHECKING:
    from app.entities.activity import Activity


class Notification(Base):
    """One activity notification belonging to one recipient."""

    __tablename__ = "notification"
    __table_args__ = (UniqueConstraint("user_id", "activity_id"),)

    user_id: Mapped[uuid.UUID] = mapped_column(UUID, ForeignKey("user.id", ondelete="CASCADE"), index=True)
    activity_id: Mapped[uuid.UUID] = mapped_column(UUID, ForeignKey("activity.id", ondelete="CASCADE"), index=True)
    reason: Mapped[str] = mapped_column(String(32))
    category: Mapped[str] = mapped_column(String(32))
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False)
    activity: Mapped["Activity"] = relationship()


class NotificationPreference(Base):
    """Account delivery preference; the inbox is always enabled."""

    __tablename__ = "notification_preference"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID, ForeignKey("user.id", ondelete="CASCADE"), unique=True)
    email: Mapped[bool] = mapped_column(Boolean, default=False)


class NotificationRepositoryPreference(Base):
    """Categories a recipient wants from a repository."""

    __tablename__ = "notification_repository_preference"
    __table_args__ = (UniqueConstraint("user_id", "repo_id"),)

    user_id: Mapped[uuid.UUID] = mapped_column(UUID, ForeignKey("user.id", ondelete="CASCADE"), index=True)
    repo_id: Mapped[uuid.UUID] = mapped_column(UUID, ForeignKey("repository.id", ondelete="CASCADE"), index=True)
    categories: Mapped[list[str]] = mapped_column(JSON)


class NotificationSubscription(Base):
    """A recipient's explicit mute setting for a discussion."""

    __tablename__ = "notification_subscription"
    __table_args__ = (UniqueConstraint("user_id", "repo_id", "thread"),)

    user_id: Mapped[uuid.UUID] = mapped_column(UUID, ForeignKey("user.id", ondelete="CASCADE"), index=True)
    repo_id: Mapped[uuid.UUID] = mapped_column(UUID, ForeignKey("repository.id", ondelete="CASCADE"), index=True)
    thread: Mapped[str] = mapped_column(String(100))
    muted: Mapped[bool] = mapped_column(Boolean, default=False)
