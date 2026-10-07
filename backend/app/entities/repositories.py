"""Repository entity model."""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import UUID, Boolean, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.entities.base import Base

if TYPE_CHECKING:
    from app.entities.activity import Activity
    from app.entities.issues import Issue
    from app.entities.principals import Principal
    from app.entities.releases import Release
    from app.entities.stars import Star
    from app.entities.watchers import Watcher


class Repository(Base):
    """Repository database model."""

    __tablename__ = "repository"
    __table_args__ = (UniqueConstraint("owner_id", "name", name="repository_owner_name_key"),)

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("principal.id"), nullable=False, index=True
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_private: Mapped[bool] = mapped_column(Boolean, default=False)
    default_branch: Mapped[str] = mapped_column(String(255), default="main")
    fork_of_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("repository.id"), nullable=True, index=True
    )

    owner: Mapped["Principal"] = relationship(back_populates="repositories")
    fork_of: Mapped["Repository | None"] = relationship(remote_side="Repository.id", back_populates="forks")
    forks: Mapped[list["Repository"]] = relationship(back_populates="fork_of")
    issues: Mapped[list["Issue"]] = relationship(back_populates="repo")
    stars: Mapped[list["Star"]] = relationship(back_populates="repo")
    watchers: Mapped[list["Watcher"]] = relationship(back_populates="repo")
    activities: Mapped[list["Activity"]] = relationship(back_populates="repo")
    releases: Mapped[list["Release"]] = relationship(back_populates="repo")
