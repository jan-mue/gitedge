"""Persistent reactions to discussion comments."""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import UUID, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.entities.base import Base

if TYPE_CHECKING:
    from app.entities.users import User


class CommentReaction(Base):
    """A user may add a given emoji to a comment once."""

    __tablename__ = "comment_reaction"
    __table_args__ = (UniqueConstraint("comment_id", "user_id", "emoji"),)

    comment_id: Mapped[uuid.UUID] = mapped_column(UUID, ForeignKey("comment.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID, ForeignKey("user.id", ondelete="CASCADE"), index=True)
    emoji: Mapped[str] = mapped_column(String(32))
    user: Mapped["User"] = relationship()
