"""Release entity model."""

import uuid
from datetime import datetime

from sqlalchemy import UUID, Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.entities.base import Base


class Release(Base):
    """A repository release tied to a Git tag."""

    __tablename__ = "release"
    __table_args__ = (UniqueConstraint("repo_id", "tag_name", name="release_repo_tag_key"),)

    repo_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("repository.id"), nullable=False, index=True
    )
    tag_name: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    author_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user.id"), nullable=True, index=True
    )
    target_commitish: Mapped[str] = mapped_column(String(255), default="main")
    is_draft: Mapped[bool] = mapped_column(Boolean, default=False)
    is_prerelease: Mapped[bool] = mapped_column(Boolean, default=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
