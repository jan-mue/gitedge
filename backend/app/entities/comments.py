"""Comment entity model."""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import UUID, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.entities.base import Base

if TYPE_CHECKING:
    from app.entities.issues import Issue
    from app.entities.reviews import PullRequestComment
    from app.entities.users import User


class Comment(Base):
    """A comment on an issue or pull request."""

    __tablename__ = "comment"

    issue_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("issue.id"), nullable=False, index=True)
    author_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("user.id"), nullable=False, index=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)

    reply_to: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("comment.id", ondelete="CASCADE"), nullable=True, index=True
    )
    parent: Mapped["Comment | None"] = relationship(remote_side="Comment.id", back_populates="replies")
    replies: Mapped[list["Comment"]] = relationship(
        back_populates="parent",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="Comment.created_at, Comment.id",
    )
    pull_request_comment: Mapped["PullRequestComment | None"] = relationship(
        back_populates="comment", cascade="all, delete-orphan", passive_deletes=True
    )

    issue: Mapped["Issue"] = relationship(back_populates="comments")
    author: Mapped["User"] = relationship(back_populates="comments")
