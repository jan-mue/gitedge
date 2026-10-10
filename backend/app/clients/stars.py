"""Star store for database operations."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.clients.database import CrudStore, SQLStore
from app.entities.stars import Star

if TYPE_CHECKING:
    import uuid
    from collections.abc import Sequence

    from sqlalchemy.ext.asyncio import AsyncSession


class StarStore(CrudStore[Star], ABC):
    """Abstract star store with star-specific queries."""

    @abstractmethod
    async def get_by_user_and_repo(self, user_id: uuid.UUID, repo_id: uuid.UUID) -> Star | None:
        """Get a star for a user and repository, if it exists."""

    @abstractmethod
    async def list_by_repo(self, repo_id: uuid.UUID, offset: int = 0, limit: int = 100) -> list[Star]:
        """List stars for a repository, newest first."""

    @abstractmethod
    async def list_by_user(self, user_id: uuid.UUID, offset: int = 0, limit: int = 100) -> list[Star]:
        """List repositories starred by a user, newest first."""

    @abstractmethod
    async def count_by_repo(self, repo_id: uuid.UUID) -> int:
        """Count stars for a repository."""

    @abstractmethod
    async def count_by_repos(self, repo_ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, int]:
        """Count stars for multiple repositories, keyed by repository id."""


class SQLStarStore(StarStore, SQLStore[Star]):
    """SQLAlchemy implementation of the star store."""

    def __init__(self, db: AsyncSession) -> None:
        """Initialize the star store.

        Args:
            db: SQLAlchemy async session.
        """
        super().__init__(db, Star)

    async def get_by_user_and_repo(self, user_id: uuid.UUID, repo_id: uuid.UUID) -> Star | None:
        """Get a star for a user and repository, if it exists."""
        return await self.db.scalar(select(Star).where(Star.user_id == user_id, Star.repo_id == repo_id))

    async def list_by_repo(self, repo_id: uuid.UUID, offset: int = 0, limit: int = 100) -> list[Star]:
        """List stars for a repository, newest first."""
        result = await self.db.scalars(
            select(Star)
            .options(selectinload(Star.user))
            .where(Star.repo_id == repo_id)
            .order_by(Star.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(result.all())

    async def list_by_user(self, user_id: uuid.UUID, offset: int = 0, limit: int = 100) -> list[Star]:
        """List repositories starred by a user, newest first."""
        result = await self.db.scalars(
            select(Star).where(Star.user_id == user_id).order_by(Star.created_at.desc()).offset(offset).limit(limit)
        )
        return list(result.all())

    async def count_by_repo(self, repo_id: uuid.UUID) -> int:
        """Count stars for a repository."""
        result = await self.db.execute(select(func.count()).select_from(Star).where(Star.repo_id == repo_id))
        return result.scalar_one()

    async def count_by_repos(self, repo_ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, int]:
        """Count stars for multiple repositories, keyed by repository id."""
        if not repo_ids:
            return {}
        result = await self.db.execute(
            select(Star.repo_id, func.count()).where(Star.repo_id.in_(repo_ids)).group_by(Star.repo_id)
        )
        return dict(result.all())
