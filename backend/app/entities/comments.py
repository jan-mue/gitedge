"""Comment entity model."""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import UUID, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.entities.base import Base

if TYPE_CHECKING:
    from app.entities.issues import Issue
    from app.entities.users import User


class Comment(Base):
    """A comment on an issue or pull request."""

    __tablename__ = "comment"

    issue_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("issue.id"), nullable=False, index=True)
    author_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("user.id"), nullable=False, index=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)

    issue: Mapped["Issue"] = relationship(back_populates="comments")
    author: Mapped["User"] = relationship(back_populates="comments")
