"""User store for database operations."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, override

from sqlalchemy import select

from app.clients.database import CrudStore, SQLStore
from app.entities.users import User
from app.exceptions import UserNotFoundError

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class UserStore(CrudStore[User], ABC):
    """Abstract user store with additional user-specific methods."""

    @abstractmethod
    async def get_by_email(self, email: str) -> User | None:
        """Get a user by their email address."""

    @abstractmethod
    async def find_by_name(self, name: str) -> User | None:
        """Find a user by their name (case-insensitive), returning None when absent."""

    async def get_by_name(self, name: str) -> User:
        """Get a user by their name (case-insensitive), raising when absent.

        Raises:
            UserNotFoundError: If no user matches the name.
        """
        user = await self.find_by_name(name)
        if user is None:
            raise UserNotFoundError
        return user


class SQLUserStore(UserStore, SQLStore[User]):
    """SQLAlchemy implementation of the user store."""

    def __init__(self, db: AsyncSession) -> None:
        """Initialize the user store.

        Args:
            db: SQLAlchemy async session.
        """
        super().__init__(db, User)

    @override
    async def get_by_email(self, email: str) -> User | None:
        """Get a user by their email address."""
        return await self.db.scalar(select(User).where(User.email == email))

    @override
    async def find_by_name(self, name: str) -> User | None:
        """Find a user by their name (case-insensitive), returning None when absent."""
        return await self.db.scalar(select(User).where(User.lower_name == name.lower()))
