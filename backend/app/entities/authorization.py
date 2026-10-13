"""Persistent organization membership, teams, and repository collaborators."""

import uuid

from sqlalchemy import UUID, Boolean, CheckConstraint, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.entities.base import Base


class OrganizationMember(Base):
    """A user belonging to an organization."""

    __tablename__ = "organization_member"
    __table_args__ = (UniqueConstraint("organization_id", "user_id"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organization.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"), index=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)


class Team(Base):
    """An organization-scoped team."""

    __tablename__ = "team"
    __table_args__ = (UniqueConstraint("organization_id", "name"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organization.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(255))


class TeamMember(Base):
    """A user belonging to a team."""

    __tablename__ = "team_member"
    __table_args__ = (UniqueConstraint("team_id", "user_id"),)

    team_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("team.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"), index=True)


class RepositoryCollaborator(Base):
    """A repository role assigned to exactly one user or team."""

    __tablename__ = "repository_collaborator"
    __table_args__ = (
        UniqueConstraint("repository_id", "user_id", name="repository_collaborator_repository_user_key"),
        UniqueConstraint("repository_id", "team_id", name="repository_collaborator_repository_team_key"),
        CheckConstraint("(user_id IS NULL) <> (team_id IS NULL)", name="one_subject"),
        CheckConstraint("role IN ('read', 'write', 'admin', 'owner')", name="valid_role"),
    )

    repository_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("repository.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID, ForeignKey("user.id", ondelete="CASCADE"), nullable=True)
    team_id: Mapped[uuid.UUID | None] = mapped_column(UUID, ForeignKey("team.id", ondelete="CASCADE"), nullable=True)
    role: Mapped[str] = mapped_column(String(20))
