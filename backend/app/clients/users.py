"""User store for database operations."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from sqlalchemy import select

from app.clients.database import CrudStore, SQLStore
from app.entities.users import User

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class UserStore(CrudStore[User], ABC):
    """Abstract user store with additional user-specific methods."""

    @abstractmethod
    async def get_by_email(self, email: str) -> User | None:
        """Get a user by their email address."""

    @abstractmethod
    async def get_by_username(self, username: str) -> User | None:
        """Get a user by their username."""


class SQLUserStore(UserStore, SQLStore[User]):
    """SQLAlchemy implementation of the user store."""

    def __init__(self, db: AsyncSession) -> None:
        """Initialize the user store.

        Args:
            db: SQLAlchemy async session.
        """
        super().__init__(db, User)

    async def get_by_email(self, email: str) -> User | None:
        """Get a user by their email address."""
        return await self.db.scalar(select(User).where(User.email == email))

    async def get_by_username(self, username: str) -> User | None:
        """Get a user by their username."""
        return await self.db.scalar(select(User).where(User.username == username))
