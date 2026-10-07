"""Comment store for database operations."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.clients.database import CrudStore, SQLStore
from app.entities.comments import Comment

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession


class CommentStore(CrudStore[Comment], ABC):
    """Abstract comment store with comment-specific queries."""

    @abstractmethod
    async def list_by_issue(self, issue_id: uuid.UUID) -> list[Comment]:
        """List comments for an issue, oldest first."""

    @abstractmethod
    async def count_by_issue(self, issue_id: uuid.UUID) -> int:
        """Count comments for an issue."""


class SQLCommentStore(CommentStore, SQLStore[Comment]):
    """SQLAlchemy implementation of the comment store."""

    def __init__(self, db: AsyncSession) -> None:
        """Initialize the comment store.

        Args:
            db: SQLAlchemy async session.
        """
        super().__init__(db, Comment)

    async def list_by_issue(self, issue_id: uuid.UUID) -> list[Comment]:
        """List comments for an issue, oldest first."""
        result = await self.db.scalars(
            select(Comment)
            .options(selectinload(Comment.author))
            .where(Comment.issue_id == issue_id)
            .order_by(Comment.created_at.asc())
        )
        return list(result.all())

    async def count_by_issue(self, issue_id: uuid.UUID) -> int:
        """Count comments for an issue."""
        result = await self.db.execute(select(func.count()).select_from(Comment).where(Comment.issue_id == issue_id))
        return result.scalar_one()
