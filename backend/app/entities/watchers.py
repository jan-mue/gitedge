"""Watcher entity model."""

import uuid

from sqlalchemy import UUID, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.entities.base import Base


class Watcher(Base):
    """A user watching a repository."""

    __tablename__ = "watcher"
    __table_args__ = (UniqueConstraint("user_id", "repo_id", name="watcher_user_repo_key"),)

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("user.id"), nullable=False, index=True)
    repo_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("repository.id"), nullable=False, index=True
    )
