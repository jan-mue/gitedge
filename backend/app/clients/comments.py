"""Comment store for database operations."""

from __future__ import annotations

from abc import ABC
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.clients.database import CrudStore, SQLStore
from app.entities.comments import Comment

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession


class CommentStore(CrudStore[Comment], ABC):
    """Abstract comment store."""


class SQLCommentStore(CommentStore, SQLStore[Comment]):
    """SQLAlchemy implementation of the comment store."""

    def __init__(self, db: AsyncSession) -> None:
        """Initialize the comment store.

        Args:
            db: SQLAlchemy async session.
        """
        super().__init__(db, Comment)

    async def find(self, primary_key: uuid.UUID) -> Comment | None:
        """Find a comment by id, loading its author."""
        return await self.db.scalar(
            select(Comment).options(selectinload(Comment.author)).where(Comment.id == primary_key)
        )
