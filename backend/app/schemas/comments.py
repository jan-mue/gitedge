"""Comment schemas."""

import uuid
from datetime import datetime

from pydantic import Field

from app.schemas.base import GitEdgeBaseModel


class CommentCreate(GitEdgeBaseModel):
    """Request to create a comment."""

    body: str = Field(min_length=1)


class CommentUpdate(GitEdgeBaseModel):
    """Request to update a comment."""

    body: str = Field(min_length=1)


class CommentPublic(GitEdgeBaseModel):
    """Public comment representation."""

    id: uuid.UUID
    author_username: str
    body: str
    body_html: str
    created_at: datetime
    updated_at: datetime


class CommentsPublic(GitEdgeBaseModel):
    """List of comments."""

    data: list[CommentPublic]
    count: int
