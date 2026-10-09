"""User entity model."""

import uuid
from typing import TYPE_CHECKING

from pydantic import EmailStr
from sqlalchemy import UUID, Boolean, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.entities.principals import Principal, PrincipalType

if TYPE_CHECKING:
    from app.entities.activity import Activity
    from app.entities.comments import Comment
    from app.entities.issues import Issue
    from app.entities.releases import Release
    from app.entities.stars import Star
    from app.entities.watchers import Watcher


class User(Principal):
    """User database model - extends Principal (joined table inheritance)."""

    __tablename__ = "user"
    __mapper_args__ = {"polymorphic_identity": PrincipalType.USER}

    # Use the same id as Principal (foreign key to Principal primary key) - override parent
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("principal.id"),
        primary_key=True,
    )

    email: Mapped[EmailStr] = mapped_column(String(255), unique=True, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False)
    hashed_password: Mapped[str] = mapped_column(Text, nullable=False)

    comments: Mapped[list["Comment"]] = relationship(back_populates="author")
    issues: Mapped[list["Issue"]] = relationship(back_populates="author")
    stars: Mapped[list["Star"]] = relationship(back_populates="user")
    watchers: Mapped[list["Watcher"]] = relationship(back_populates="user")
    activities: Mapped[list["Activity"]] = relationship(back_populates="actor")
    releases: Mapped[list["Release"]] = relationship(back_populates="author")
