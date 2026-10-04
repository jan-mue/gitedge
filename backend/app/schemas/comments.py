"""Comment schemas."""

import uuid
from datetime import datetime

from pydantic import Field

from app.schemas.base import GitEdgeBaseModel


class CommentCreate(GitEdgeBaseModel):
    """Request to create a comment."""

    body: str = Field(min_length=1)


class CommentPublic(GitEdgeBaseModel):
    """Public comment representation."""

    id: uuid.UUID
    repo_path: str
    issue_number: int
    author_email: str | None = None
    author_username: str | None = None
    body: str
    created_at: datetime | None = None
    updated_at: datetime | None = None


class CommentsPublic(GitEdgeBaseModel):
    """List of comments."""

    data: list[CommentPublic]
    count: int
