"""Activity store for database operations."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from sqlalchemy import select

from app.clients.database import CrudStore, SQLStore
from app.entities.activity import Activity

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession


class ActivityStore(CrudStore[Activity], ABC):
    """Abstract activity store with activity-specific queries."""

    @abstractmethod
    async def list_recent(self, offset: int = 0, limit: int = 50) -> list[Activity]:
        """List recent activity across all repositories, newest first."""

    @abstractmethod
    async def list_by_repo(self, repo_id: uuid.UUID, offset: int = 0, limit: int = 50) -> list[Activity]:
        """List activity for a repository, newest first."""

    @abstractmethod
    async def list_by_repos(self, repo_ids: list[uuid.UUID], offset: int = 0, limit: int = 50) -> list[Activity]:
        """List activity for a set of repositories, newest first."""


class SQLActivityStore(ActivityStore, SQLStore[Activity]):
    """SQLAlchemy implementation of the activity store."""

    def __init__(self, db: AsyncSession) -> None:
        """Initialize the activity store.

        Args:
            db: SQLAlchemy async session.
        """
        super().__init__(db, Activity)

    async def list_recent(self, offset: int = 0, limit: int = 50) -> list[Activity]:
        """List recent activity across all repositories, newest first."""
        result = await self.db.scalars(
            select(Activity).order_by(Activity.created_at.desc()).offset(offset).limit(limit)
        )
        return list(result.all())

    async def list_by_repo(self, repo_id: uuid.UUID, offset: int = 0, limit: int = 50) -> list[Activity]:
        """List activity for a repository, newest first."""
        result = await self.db.scalars(
            select(Activity)
            .where(Activity.repo_id == repo_id)
            .order_by(Activity.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(result.all())

    async def list_by_repos(self, repo_ids: list[uuid.UUID], offset: int = 0, limit: int = 50) -> list[Activity]:
        """List activity for a set of repositories, newest first."""
        if not repo_ids:
            return []
        result = await self.db.scalars(
            select(Activity)
            .where(Activity.repo_id.in_(repo_ids))
            .order_by(Activity.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(result.all())
