"""CRUD service for user operations."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.entities.users import User
from app.schemas.users import UserCreate, UserPublic, UserUpdate, UserUpdateMe
from app.utils.security import get_password_hash, verify_password

if TYPE_CHECKING:
    import uuid

    from app.clients.users import UserRepository

# Dummy hash to use for timing attack prevention when user is not found
# This is an Argon2 hash of a random password, used to ensure constant-time comparison
DUMMY_HASH = "$argon2id$v=19$m=65536,t=3,p=4$MjQyZWE1MzBjYjJlZTI0Yw$YTU4NGM5ZTZmYjE2NzZlZjY0ZWY3ZGRkY2U2OWFjNjk"


class CrudService:
    """Service for CRUD operations on users."""

    def __init__(self, user_repository: UserRepository) -> None:
        """Initialize the CRUD service.

        Args:
            user_repository: Repository for user database operations.
        """
        self.user_repository = user_repository

    def create_user(self, user_create: UserCreate) -> UserPublic:
        """Create a new user.

        Args:
            user_create: User creation data.

        Returns:
            The created user's public data.
        """
        user = User(
            email=user_create.email,
            full_name=user_create.full_name,
            is_superuser=user_create.is_superuser,
            is_active=user_create.is_active,
            hashed_password=get_password_hash(user_create.password),
        )
        self.user_repository.add(user)
        return UserPublic.model_validate(user)

    def get_user_by_id(self, user_id: uuid.UUID) -> UserPublic | None:
        """Get a user by their ID.

        Args:
            user_id: The user's UUID.

        Returns:
            The user's public data or None if not found.
        """
        user = self.user_repository.get(user_id)
        if not user:
            return None
        return UserPublic.model_validate(user)

    def get_user_by_email(self, email: str) -> UserPublic | None:
        """Get a user by their email.

        Args:
            email: The user's email address.

        Returns:
            The user's public data or None if not found.
        """
        user = self.user_repository.get_by_email(email)
        if not user:
            return None
        return UserPublic.model_validate(user)

    def update_user(self, db_user: User, user_in: UserUpdate | UserUpdateMe) -> UserPublic:
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
        self.user_repository.update(db_user, user_data)
        return UserPublic.model_validate(db_user)

    def authenticate(self, email: str, password: str) -> User | None:
        """Authenticate a user by email and password.

        Args:
            email: The user's email.
            password: The user's password.

        Returns:
            The user entity if authentication succeeds, None otherwise.
        """
        db_user = self.user_repository.get_by_email(email)
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
            self.user_repository.update(db_user)
        return db_user
