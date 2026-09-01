"""Token and authentication schemas."""

from pydantic import BaseModel, Field


class Token(BaseModel):
    """OAuth2 token response schema."""

    access_token: str
    token_type: str = "bearer"  # noqa: S105


class TokenPayload(BaseModel):
    """JWT token payload schema."""

    sub: str | None = None


class NewPassword(BaseModel):
    """Schema for password reset with token."""

    token: str
    new_password: str = Field(min_length=8, max_length=40)
