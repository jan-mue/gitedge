"""User store for database operations."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from sqlalchemy import select

from app.clients.database import CrudStore, SQLStore
from app.entities.users import User

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


class UserStore(CrudStore[User], ABC):
    """Abstract user store with additional user-specific methods."""

    @abstractmethod
    def get_by_email(self, email: str) -> User | None:
        """Get a user by their email address."""


class SQLUserStore(UserStore, SQLStore[User]):
    """SQLAlchemy implementation of the user store."""

    def __init__(self, db: Session) -> None:
        """Initialize the user store.

        Args:
            db: SQLAlchemy session.
        """
        super().__init__(db, User)

    def get_by_email(self, email: str) -> User | None:
        """Get a user by their email address."""
        return self.db.scalar(select(User).where(User.email == email))
