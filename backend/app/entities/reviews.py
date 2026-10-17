"""Persisted pull request reviews and private review workspaces."""

import uuid
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, UUID, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.entities.base import Base
from app.entities.enums import string_enum

if TYPE_CHECKING:
    from app.entities.comments import Comment
    from app.entities.users import User


class ReviewState(StrEnum):
    """The outcome of a submitted review."""

    APPROVED = "approved"
    COMMENT = "comment"
    CHANGES_REQUESTED = "changes_requested"


class DiffSide(StrEnum):
    """The original or updated side of a line comment."""

    OLD = "old"
    NEW = "new"


class PullRequestReview(Base):
    """A review outcome and the immutable revisions reviewed."""

    __tablename__ = "pull_request_review"

    pull_request_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pull_request.id", ondelete="CASCADE"), index=True
    )
    author_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("user.id"))
    state: Mapped[ReviewState] = mapped_column(string_enum(ReviewState))
    base_commit: Mapped[str] = mapped_column(String(40))
    head_commit: Mapped[str] = mapped_column(String(40))
    author: Mapped["User"] = relationship()
    comments: Mapped[list["PullRequestComment"]] = relationship(
        back_populates="review", cascade="all, delete-orphan", order_by="PullRequestComment.position"
    )

    @property
    def summary(self) -> Comment | None:
        """The optional overall comment, stored alongside all other comments."""
        return next((link.comment for link in self.comments if link.path is None), None)

    @property
    def body(self) -> str:
        """Expose the overall comment body without duplicating its storage."""
        return self.summary.body if self.summary is not None else ""

    @property
    def line_comments(self) -> list[PullRequestComment]:
        """The ordered line anchors belonging to this review."""
        return [link for link in self.comments if link.path is not None]


class PullRequestComment(Base):
    """Associate a regular comment with a review and optional diff anchor.

    Text, author and replies live in Comment; the bounded context snapshot remains
    available after a force-push or deletion of the PR branch. Position -1 is the
    overall review comment; nonnegative positions identify its line comments.
    """

    __tablename__ = "pull_request_comments"
    __table_args__ = (
        UniqueConstraint("comment_id"),
        UniqueConstraint("review_id", "position"),
    )

    review_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pull_request_review.id", ondelete="CASCADE"), index=True
    )
    comment_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("comment.id", ondelete="CASCADE"))
    position: Mapped[int] = mapped_column(Integer)
    path: Mapped[str | None] = mapped_column(String(4096))
    side: Mapped[DiffSide | None] = mapped_column(string_enum(DiffSide))
    line: Mapped[int | None] = mapped_column(Integer)
    context: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    comment: Mapped["Comment"] = relationship(back_populates="pull_request_comment")
    review: Mapped["PullRequestReview"] = relationship(back_populates="comments")


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
