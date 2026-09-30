"""Token and authentication schemas."""

import uuid

from pydantic import Field

from app.schemas.base import GitEdgeBaseModel


class Token(GitEdgeBaseModel):
    """OAuth2 token response schema."""

    access_token: str
    token_type: str = "bearer"  # noqa: S105


class TokenPayload(GitEdgeBaseModel):
    """JWT token payload schema."""

    sub: uuid.UUID | None = None


class NewPassword(GitEdgeBaseModel):
    """Schema for password reset with token."""

    token: str
    new_password: str = Field(min_length=8, max_length=40)
