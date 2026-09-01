"""Security utilities for password hashing and JWT tokens."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import jwt
from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher
from pwdlib.hashers.bcrypt import BcryptHasher

from app.config import settings

if TYPE_CHECKING:
    import uuid

password_hash = PasswordHash(
    (
        Argon2Hasher(),
        BcryptHasher(),
    )
)


ALGORITHM = "HS256"


def create_access_token(subject: str | uuid.UUID, expires_delta: timedelta) -> str:
    """Create a JWT access token.

    Args:
        subject: The subject to encode in the token (usually user ID).
        expires_delta: How long until the token expires.

    Returns:
        The encoded JWT token string.
    """
    expire = datetime.now(UTC) + expires_delta
    to_encode = {"exp": expire, "sub": str(subject)}
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)


def verify_password(plain_password: str, hashed_password: str) -> tuple[bool, str | None]:
    """Verify a plain password against a hashed password.

    Only supports bcrypt hashes.

    Args:
        plain_password: The plain text password.
        hashed_password: The hashed password to compare against.

    Returns:
        Tuple of (verified: bool, updated_hash: str | None).
        The updated_hash is provided if the hash needs to be updated (e.g., cost factor changed).
    """
    return password_hash.verify_and_update(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash a password using bcrypt.

    Args:
        password: The plain text password to hash.

    Returns:
        The bcrypt hashed password.
    """
    return password_hash.hash(password)
