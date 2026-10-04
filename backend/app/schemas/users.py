"""User Pydantic schemas."""

import uuid

from pydantic import ConfigDict, EmailStr, Field

from app.schemas.base import GitEdgeBaseModel


class UserBase(GitEdgeBaseModel):
    """Base user schema with common fields."""

    username: str | None = Field(default=None, max_length=255)
    email: EmailStr = Field(max_length=255)
    is_active: bool = True
    is_superuser: bool = False
    full_name: str | None = Field(default=None, max_length=255)


class UserCreate(UserBase):
    """Schema for creating a new user."""

    model_config = ConfigDict(from_attributes=True)

    password: str = Field(min_length=8, max_length=40)


class UserRegister(GitEdgeBaseModel):
    """Schema for user self-registration."""

    username: str | None = Field(default=None, max_length=255)
    email: EmailStr = Field(max_length=255)
    password: str = Field(min_length=8, max_length=40)
    full_name: str | None = Field(default=None, max_length=255)


class UserUpdate(UserBase):
    """Schema for updating a user (admin)."""

    email: EmailStr | None = Field(default=None, max_length=255)  # type: ignore[assignment]
    password: str | None = Field(default=None, min_length=8, max_length=40)


class UserUpdateMe(GitEdgeBaseModel):
    """Schema for users updating their own profile."""

    full_name: str | None = Field(default=None, max_length=255)
    email: EmailStr | None = Field(default=None, max_length=255)
    username: str | None = Field(default=None, max_length=255)


class UpdatePassword(GitEdgeBaseModel):
    """Schema for password update."""

    current_password: str = Field(min_length=8, max_length=40)
    new_password: str = Field(min_length=8, max_length=40)


class UserPublic(UserBase):
    """Schema for returning user data to clients."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID


class UsersPublic(GitEdgeBaseModel):
    """Schema for paginated list of users."""

    data: list[UserPublic]
    count: int
