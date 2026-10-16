"""Persisted pull request reviews and private review workspaces."""

import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, UUID, ForeignKey, Integer, String, Text, UniqueConstraint
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
    comments: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    author: Mapped["User"] = relationship()
    replies: Mapped[list["PullRequestReviewReply"]] = relationship(
        back_populates="review",
        cascade="all, delete-orphan",
        order_by="PullRequestReviewReply.created_at, PullRequestReviewReply.id",
    )


class PullRequestReviewReply(Base):
    """A published reply to an immutable review comment or its overall body."""

    __tablename__ = "pull_request_review_reply"

    review_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pull_request_review.id", ondelete="CASCADE"), index=True
    )
    author_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("user.id"))
    comment_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    body: Mapped[str] = mapped_column(Text)
    author: Mapped["User"] = relationship()
    review: Mapped["PullRequestReview"] = relationship(back_populates="replies")


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
