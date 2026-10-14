"""Typed inputs and outputs for membership and collaborator management."""

import uuid
from enum import StrEnum

from pydantic import ConfigDict, Field, model_validator

from app.schemas.base import GitEdgeBaseModel


class RepositoryRole(StrEnum):
    """Repository collaborator roles, ordered by the policy file."""

    READ = "read"
    WRITE = "write"
    ADMIN = "admin"
    OWNER = "owner"


class CollaboratorInput(GitEdgeBaseModel):
    """A role assigned to exactly one user or team."""

    user_id: uuid.UUID | None = None
    team_id: uuid.UUID | None = None
    role: RepositoryRole

    @model_validator(mode="after")
    def one_subject(self) -> CollaboratorInput:
        """Require one collaborator subject."""
        if (self.user_id is None) == (self.team_id is None):
            raise ValueError("Specify exactly one of user_id or team_id")
        return self


class CollaboratorPublic(CollaboratorInput):
    """An explicit persisted collaborator."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    subject_name: str


class RepositoryPermissions(GitEdgeBaseModel):
    """The current viewer's effective repository permissions."""

    read: bool
    write: bool
    admin: bool
    owner: bool


class MemberInput(GitEdgeBaseModel):
    """Organization membership options."""

    is_admin: bool = False


class MemberPublic(MemberInput):
    """A member of an organization."""

    model_config = ConfigDict(from_attributes=True)

    user_id: uuid.UUID


class TeamInput(GitEdgeBaseModel):
    """Team creation options."""

    name: str = Field(min_length=1, max_length=255, pattern=r"^[A-Za-z0-9_-]+$")


class TeamPublic(TeamInput):
    """A team belonging to an organization."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
