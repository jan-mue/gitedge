"""Personal access token metadata and one-way secret hashes."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.entities.base import Base


class PersonalAccessToken(Base):
    """A revocable, scoped credential belonging to an account."""

    __tablename__ = "personal_access_token"

    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    prefix: Mapped[str] = mapped_column(String(32))
    key_id: Mapped[str] = mapped_column(String(24), unique=True, index=True)
    secret_hash: Mapped[str] = mapped_column(String(512))
    secret_last4: Mapped[str] = mapped_column(String(4))
    scopes: Mapped[list[str]] = mapped_column(JSONB)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_reason: Mapped[str | None] = mapped_column(String(200), nullable=True)
    authentication_window_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    authentication_attempts: Mapped[int] = mapped_column(Integer, default=0)
