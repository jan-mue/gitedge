"""Watcher store for database operations."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.clients.database import CrudStore, SQLStore
from app.entities.watchers import Watcher

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession


class WatcherStore(CrudStore[Watcher], ABC):
    """Abstract watcher store with watcher-specific queries."""

    @abstractmethod
    async def get_by_user_and_repo(self, user_id: uuid.UUID, repo_id: uuid.UUID) -> Watcher | None:
        """Get a watcher for a user and repository, if it exists."""

    @abstractmethod
    async def list_by_repo(self, repo_id: uuid.UUID, offset: int = 0, limit: int = 100) -> list[Watcher]:
        """List watchers for a repository, newest first."""

    @abstractmethod
    async def count_by_repo(self, repo_id: uuid.UUID) -> int:
        """Count watchers for a repository."""


class SQLWatcherStore(WatcherStore, SQLStore[Watcher]):
    """SQLAlchemy implementation of the watcher store."""

    def __init__(self, db: AsyncSession) -> None:
        """Initialize the watcher store.

        Args:
            db: SQLAlchemy async session.
        """
        super().__init__(db, Watcher)

    async def get_by_user_and_repo(self, user_id: uuid.UUID, repo_id: uuid.UUID) -> Watcher | None:
        """Get a watcher for a user and repository, if it exists."""
        return await self.db.scalar(select(Watcher).where(Watcher.user_id == user_id, Watcher.repo_id == repo_id))

    async def list_by_repo(self, repo_id: uuid.UUID, offset: int = 0, limit: int = 100) -> list[Watcher]:
        """List watchers for a repository, newest first."""
        result = await self.db.scalars(
            select(Watcher)
            .options(selectinload(Watcher.user))
            .where(Watcher.repo_id == repo_id)
            .order_by(Watcher.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(result.all())

    async def count_by_repo(self, repo_id: uuid.UUID) -> int:
        """Count watchers for a repository."""
        result = await self.db.execute(select(func.count()).select_from(Watcher).where(Watcher.repo_id == repo_id))
        return result.scalar_one()
