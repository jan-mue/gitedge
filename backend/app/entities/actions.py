"""Durable Actions run snapshots; no resident worker owns this state."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import UUID, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.entities.base import Base


class WorkflowRun(Base):
    """An immutable workflow/source revision with a reconciled job state."""

    __tablename__ = "workflow_run"
    __table_args__ = (UniqueConstraint("repo_id", "event_key", "workflow"),)

    repo_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("repository.id", ondelete="CASCADE"), index=True
    )
    workflow: Mapped[str] = mapped_column(String(512))
    definition: Mapped[str] = mapped_column(Text)
    compiled: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    name: Mapped[str] = mapped_column(String(512))
    sha: Mapped[str] = mapped_column(String(40))
    ref: Mapped[str] = mapped_column(String(512))
    actor: Mapped[str] = mapped_column(String(255))
    event_name: Mapped[str] = mapped_column(String(64))
    event_key: Mapped[str] = mapped_column(String(255))
    event: Mapped[dict[str, Any]] = mapped_column(JSONB)
    provider: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(32), index=True)
    jobs: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error: Mapped[str | None] = mapped_column(Text)
