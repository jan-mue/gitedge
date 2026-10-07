"""CRUD service for user operations."""

from __future__ import annotations

import re
import uuid
from typing import TYPE_CHECKING

from fastapi import HTTPException

from app.entities.users import User
from app.schemas.users import UserCreate, UserPublic, UserUpdate, UserUpdateMe
from app.utils.security import get_password_hash, verify_password

if TYPE_CHECKING:
    from app.clients.organizations import OrganizationStore
    from app.clients.users import UserStore

# Dummy hash to use for timing attack prevention when user is not found
# This is an Argon2 hash of a random password, used to ensure constant-time comparison
DUMMY_HASH = "$argon2id$v=19$m=65536,t=3,p=4$MjQyZWE1MzBjYjJlZTI0Yw$YTU4NGM5ZTZmYjE2NzZlZjY0ZWY3ZGRkY2U2OWFjNjk"


class CrudService:
    """Service for CRUD operations on users."""

    def __init__(self, user_store: UserStore, organization_store: OrganizationStore | None = None) -> None:
        """Initialize the CRUD service.

        Args:
            user_store: Store for user database operations.
            organization_store: Optional organization store used to keep the owner namespace unique.
        """
        self.user_store = user_store
        self.organization_store = organization_store

    async def _owner_name_taken(self, name: str, *, exclude_user_id: uuid.UUID | None = None) -> bool:
        """Check whether an owner name is already used by a user or organization.

        Args:
            name: The candidate owner name.
            exclude_user_id: A user id to ignore (when updating that user).

        Returns:
            True if the name is taken by another user or an organization.
        """
        existing = await self.user_store.get_by_name(name)
        if existing is not None and existing.id != exclude_user_id:
            return True
        return self.organization_store is not None and await self.organization_store.get_by_name(name) is not None

    async def create_user(self, user_create: UserCreate) -> UserPublic:
        """Create a new user.

        Args:
            user_create: User creation data.

        Returns:
            The created user's public data.
        """
        name = user_create.name or self._slug_from_email(user_create.email)
        if await self._owner_name_taken(name):
            name = f"{name}-{uuid.uuid4().hex[:6]}"

        user = User(
            name=name,
            lower_name=name.lower(),
            display_name=user_create.display_name,
            email=user_create.email,
            is_superuser=user_create.is_superuser,
            is_active=user_create.is_active,
            hashed_password=get_password_hash(user_create.password),
        )
        await self.user_store.add(user)
        return UserPublic.model_validate(user)

    @staticmethod
    def _slug_from_email(email: str) -> str:
        """Derive a name slug from an email address.

        Args:
            email: The user's email address.

        Returns:
            A lowercase alphanumeric slug.
        """
        local_part = email.split("@", maxsplit=1)[0]
        slug = re.sub(r"[^a-zA-Z0-9]+", "-", local_part).strip("-").lower()
        return slug or uuid.uuid4().hex[:12]

    async def get_user_by_id(self, user_id: uuid.UUID) -> UserPublic | None:
        """Get a user by their ID.

        Args:
            user_id: The user's UUID.

        Returns:
            The user's public data or None if not found.
        """
        user = await self.user_store.get(user_id)
        if not user:
            return None
        return UserPublic.model_validate(user)

    async def get_user_by_email(self, email: str) -> UserPublic | None:
        """Get a user by their email.

        Args:
            email: The user's email address.

        Returns:
            The user's public data or None if not found.
        """
        user = await self.user_store.get_by_email(email)
        if not user:
            return None
        return UserPublic.model_validate(user)

    async def update_user(self, db_user: User, user_in: UserUpdate | UserUpdateMe) -> UserPublic:
        """Update a user.

        Args:
            db_user: The user entity to update.
            user_in: The update data.

        Returns:
            The updated user's public data.
        """
        user_data = user_in.model_dump(exclude_unset=True)
        if "password" in user_data:
            password = user_data.pop("password")
            hashed_password = get_password_hash(password)
            user_data["hashed_password"] = hashed_password
        if user_data.get("name"):
            if await self._owner_name_taken(user_data["name"], exclude_user_id=db_user.id):
                raise HTTPException(status_code=409, detail="User with this name already exists")
            user_data["lower_name"] = user_data["name"].lower()
        await self.user_store.update(db_user, user_data)
        return UserPublic.model_validate(db_user)

    async def authenticate(self, email: str, password: str) -> User | None:
        """Authenticate a user by email and password.

        Args:
            email: The user's email.
            password: The user's password.

        Returns:
            The user entity if authentication succeeds, None otherwise.
        """
        db_user = await self.user_store.get_by_email(email)
        if not db_user:
            # Prevent timing attacks by running password verification even when user doesn't exist
            # This ensures the response time is similar whether or not the email exists
            verify_password(password, DUMMY_HASH)
            return None
        verified, updated_password_hash = verify_password(password, db_user.hashed_password)
        if not verified:
            return None
        if updated_password_hash:
            db_user.hashed_password = updated_password_hash
            await self.user_store.update(db_user)
        return db_user
