"""Organization Pydantic schemas."""

import uuid
from datetime import datetime

from pydantic import ConfigDict, Field

from app.schemas.base import GitEdgeBaseModel


class OrganizationCreate(GitEdgeBaseModel):
    """Request to create a new organization."""

    name: str = Field(min_length=1, max_length=255)
    display_name: str | None = Field(default=None, max_length=255)
    description: str | None = None


class OrganizationPublic(GitEdgeBaseModel):
    """Public organization representation."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    display_name: str | None = None
    description: str | None = None
    created_at: datetime


class OrganizationsPublic(GitEdgeBaseModel):
    """List of organizations."""

    data: list[OrganizationPublic]
    count: int
