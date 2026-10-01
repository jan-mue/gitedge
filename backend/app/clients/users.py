"""User repository for database operations."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from sqlalchemy import select

from app.clients.database import CrudRepository, SQLRepository
from app.entities.users import User

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


class UserRepository(CrudRepository[User], ABC):
    """Abstract user repository with additional user-specific methods."""

    @abstractmethod
    def get_by_email(self, email: str) -> User | None:
        """Get a user by their email address."""


class SQLUserRepository(UserRepository, SQLRepository[User]):
    """SQLAlchemy implementation of user repository."""

    def __init__(self, db: Session) -> None:
        """Initialize the user repository.

        Args:
            db: SQLAlchemy session.
        """
        super().__init__(db, User)

    def get_by_email(self, email: str) -> User | None:
        """Get a user by their email address."""
        return self.db.scalar(select(User).where(User.email == email))
