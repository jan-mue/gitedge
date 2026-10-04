"""Repository store for database operations."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from sqlalchemy import func, select

from app.clients.database import CrudStore, SQLStore
from app.entities.repositories import Repository

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession


class RepositoryStore(CrudStore[Repository], ABC):
    """Abstract repository store with additional repository-specific methods."""

    @abstractmethod
    async def get_by_path(self, path: str) -> Repository | None:
        """Get a repository by its path (e.g. 'owner/repo.git')."""

    @abstractmethod
    async def get_by_owner(self, owner_id: uuid.UUID, offset: int = 0, limit: int = 100) -> list[Repository]:
        """Get all repositories owned by a user."""

    @abstractmethod
    async def list_by_fork_of(self, fork_of_id: uuid.UUID, offset: int = 0, limit: int = 100) -> list[Repository]:
        """Get all repositories forked from a given repository."""

    @abstractmethod
    async def count_by_fork_of(self, fork_of_id: uuid.UUID) -> int:
        """Count repositories forked from a given repository."""


class SQLRepositoryStore(RepositoryStore, SQLStore[Repository]):
    """SQLAlchemy implementation of repository store."""

    def __init__(self, db: AsyncSession) -> None:
        """Initialize the repository store.

        Args:
            db: SQLAlchemy async session.
        """
        super().__init__(db, Repository)

    async def get_by_path(self, path: str) -> Repository | None:
        """Get a repository by its path."""
        return await self.db.scalar(select(Repository).where(Repository.path == path))

    async def get_by_owner(self, owner_id: uuid.UUID, offset: int = 0, limit: int = 100) -> list[Repository]:
        """Get all repositories owned by a user."""
        result = await self.db.scalars(
            select(Repository).where(Repository.owner_id == owner_id).offset(offset).limit(limit)
        )
        return list(result.all())

    async def list_by_fork_of(self, fork_of_id: uuid.UUID, offset: int = 0, limit: int = 100) -> list[Repository]:
        """Get all repositories forked from a given repository."""
        result = await self.db.scalars(
            select(Repository)
            .where(Repository.fork_of_id == fork_of_id)
            .order_by(Repository.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(result.all())

    async def count_by_fork_of(self, fork_of_id: uuid.UUID) -> int:
        """Count repositories forked from a given repository."""
        result = await self.db.execute(
            select(func.count()).select_from(Repository).where(Repository.fork_of_id == fork_of_id)
        )
        return result.scalar_one()
