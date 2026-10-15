"""Persisted pull request reviews and private review workspaces."""

import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, UUID, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.entities.base import Base

if TYPE_CHECKING:
    from app.entities.users import User


class PullRequestReview(Base):
    """An immutable review with its line comments and comparison revisions."""

    __tablename__ = "pull_request_review"

    pull_request_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pull_request.id", ondelete="CASCADE"), index=True
    )
    author_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("user.id"))
    state: Mapped[str] = mapped_column(String(32))
    body: Mapped[str] = mapped_column(Text, default="")
    base_commit: Mapped[str] = mapped_column(String(40))
    head_commit: Mapped[str] = mapped_column(String(40))
    comments: Mapped[list[dict[str, str | int]]] = mapped_column(JSON, default=list)
    author: Mapped["User"] = relationship()


class PullRequestReviewWorkspace(Base):
    """One private draft and viewed-file set per user and pull request."""

    __tablename__ = "pull_request_review_workspace"
    __table_args__ = (UniqueConstraint("pull_request_id", "author_id"),)

    pull_request_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pull_request.id", ondelete="CASCADE")
    )
    author_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("user.id"))
    draft: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    base_commit: Mapped[str | None] = mapped_column(String(40), nullable=True)
    head_commit: Mapped[str | None] = mapped_column(String(40), nullable=True)
    reviewed_paths: Mapped[list[str]] = mapped_column(JSON, default=list)
