"""User Pydantic schemas."""

import uuid

from pydantic import ConfigDict, EmailStr, Field

from app.entities.principals import PrincipalType
from app.schemas.base import GitEdgeBaseModel


class UserBase(GitEdgeBaseModel):
    """Base user schema with common fields."""

    email: EmailStr = Field(max_length=255)
    is_active: bool = True
    is_superuser: bool = False
    display_name: str | None = Field(default=None, max_length=255)


class UserCreate(UserBase):
    """Schema for creating a new user."""

    model_config = ConfigDict(from_attributes=True)

    name: str | None = Field(default=None, max_length=255)
    password: str = Field(min_length=8, max_length=40)


class UserRegister(GitEdgeBaseModel):
    """Schema for user self-registration."""

    name: str | None = Field(default=None, max_length=255)
    display_name: str | None = Field(default=None, max_length=255)
    email: EmailStr = Field(max_length=255)
    password: str = Field(min_length=8, max_length=40)


class UserUpdate(UserBase):
    """Schema for updating a user (admin)."""

    name: str | None = Field(default=None, max_length=255)
    email: EmailStr | None = Field(default=None, max_length=255)  # type: ignore[assignment]
    password: str | None = Field(default=None, min_length=8, max_length=40)


class UserUpdateMe(GitEdgeBaseModel):
    """Schema for users updating their own profile."""

    name: str | None = Field(default=None, max_length=255)
    display_name: str | None = Field(default=None, max_length=255)
    email: EmailStr | None = Field(default=None, max_length=255)


class UpdatePassword(GitEdgeBaseModel):
    """Schema for password update."""

    current_password: str = Field(min_length=8, max_length=40)
    new_password: str = Field(min_length=8, max_length=40)


class UserPublic(UserBase):
    """Schema for returning user data to clients."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str = Field(max_length=255)


class ProfilePublic(GitEdgeBaseModel):
    """Public profile for a principal (user or organization)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str = Field(max_length=255)
    display_name: str | None = Field(default=None, max_length=255)
    principal_type: PrincipalType


class UsersPublic(GitEdgeBaseModel):
    """Schema for paginated list of users."""

    data: list[UserPublic]
    count: int
