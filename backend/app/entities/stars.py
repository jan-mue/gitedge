"""Star entity model."""

import uuid

from sqlalchemy import UUID, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.entities.base import Base


class Star(Base):
    """A user starring a repository."""

    __tablename__ = "star"
    __table_args__ = (UniqueConstraint("user_id", "repo_id", name="star_user_repo_key"),)

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("user.id"), nullable=False, index=True)
    repo_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("repository.id"), nullable=False, index=True
    )
