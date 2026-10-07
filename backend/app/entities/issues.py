"""Issue entity model."""

import uuid
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import UUID, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.entities.base import Base

if TYPE_CHECKING:
    from app.entities.comments import Comment
    from app.entities.repositories import Repository
    from app.entities.users import User


class IssueKind(StrEnum):
    """Kinds of issue-tracker records."""

    ISSUE = "issue"
    PULL_REQUEST = "pull_request"


class IssueState(StrEnum):
    """State of an issue or pull request."""

    OPEN = "open"
    CLOSED = "closed"
    MERGED = "merged"


class Issue(Base):
    """Issue database model."""

    __tablename__ = "issue"
    __table_args__ = (UniqueConstraint("repo_id", "number", name="issue_repo_number_key"),)
    __mapper_args__ = {"polymorphic_identity": IssueKind.ISSUE, "polymorphic_on": "kind"}

    repo_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("repository.id"), nullable=False, index=True
    )
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    state: Mapped[IssueState] = mapped_column(String(20), default=IssueState.OPEN)
    author_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("user.id"), nullable=False, index=True)
    kind: Mapped[IssueKind] = mapped_column("type", String(20), default=IssueKind.ISSUE)

    repo: Mapped["Repository"] = relationship(back_populates="issues")
    author: Mapped["User"] = relationship(back_populates="issues")
    comments: Mapped[list["Comment"]] = relationship(back_populates="issue")
