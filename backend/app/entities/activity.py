"""Activity entity model for the feed."""

import uuid

from sqlalchemy import UUID, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.entities.base import Base


class Activity(Base):
    """A recorded activity event shown in user and repository feeds."""

    __tablename__ = "activity"

    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user.id"), nullable=True, index=True
    )
    actor_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    repo_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("repository.id"), nullable=True, index=True
    )
    kind: Mapped[str] = mapped_column(String(40), nullable=False)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    target_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    target_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
