"""Issue entity model."""

import uuid

from sqlalchemy import UUID, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.entities.base import Base


class Issue(Base):
    """Issue database model."""

    __tablename__ = "issue"
    __table_args__ = (UniqueConstraint("repo_id", "number", name="issue_repo_number_key"),)

    repo_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("repository.id"), nullable=False, index=True
    )
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    state: Mapped[str] = mapped_column(String(20), default="open")
    author_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
