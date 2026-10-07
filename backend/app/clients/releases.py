"""Release store for database operations."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.clients.database import CrudStore, SQLStore
from app.entities.releases import Release
from app.exceptions import ReleaseNotFoundError

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession


class ReleaseStore(CrudStore[Release], ABC):
    """Abstract release store with release-specific queries."""

    @abstractmethod
    async def list_by_repo(self, repo_id: uuid.UUID, include_drafts: bool = False) -> list[Release]:
        """List releases for a repository, newest first."""

    @abstractmethod
    async def get_by_tag(self, repo_id: uuid.UUID, tag_name: str) -> Release:
        """Get a release by repository id and tag name, raising when absent."""

    @abstractmethod
    async def find_by_tag(self, repo_id: uuid.UUID, tag_name: str) -> Release | None:
        """Find a release by repository id and tag name, or None."""


class SQLReleaseStore(ReleaseStore, SQLStore[Release]):
    """SQLAlchemy implementation of the release store."""

    def __init__(self, db: AsyncSession) -> None:
        """Initialize the release store.

        Args:
            db: SQLAlchemy async session.
        """
        super().__init__(db, Release)

    async def list_by_repo(self, repo_id: uuid.UUID, include_drafts: bool = False) -> list[Release]:
        """List releases for a repository, newest first."""
        stmt = select(Release).options(selectinload(Release.author)).where(Release.repo_id == repo_id)
        if not include_drafts:
            stmt = stmt.where(Release.is_draft.is_(False))
        stmt = stmt.order_by(Release.created_at.desc())
        result = await self.db.scalars(stmt)
        return list(result.all())

    async def find_by_tag(self, repo_id: uuid.UUID, tag_name: str) -> Release | None:
        """Find a release by repository id and tag name, or None."""
        return await self.db.scalar(
            select(Release)
            .options(selectinload(Release.author))
            .where(Release.repo_id == repo_id, Release.tag_name == tag_name)
        )

    async def get_by_tag(self, repo_id: uuid.UUID, tag_name: str) -> Release:
        """Get a release by repository id and tag name, raising when absent."""
        release = await self.find_by_tag(repo_id, tag_name)
        if release is None:
            raise ReleaseNotFoundError
        return release
