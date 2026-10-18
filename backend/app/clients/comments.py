"""Comment store for database operations."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, override

from sqlalchemy import select
from sqlalchemy.orm import joinedload, selectinload

from app.clients.database import CrudStore, SQLStore
from app.entities.comments import Comment

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession


class CommentStore(CrudStore[Comment], ABC):
    """Abstract comment store."""

    @abstractmethod
    async def list_by_issue(self, issue_id: uuid.UUID) -> list[Comment]:
        """Load discussion comments and their authors only when explicitly requested."""


class SQLCommentStore(CommentStore, SQLStore[Comment]):
    """SQLAlchemy implementation of the comment store."""

    def __init__(self, db: AsyncSession) -> None:
        """Initialize the comment store.

        Args:
            db: SQLAlchemy async session.
        """
        super().__init__(db, Comment)

    @override
    async def find(self, primary_key: uuid.UUID) -> Comment | None:
        """Find a comment by id, loading its author."""
        return await self.db.scalar(
            select(Comment).options(selectinload(Comment.author)).where(Comment.id == primary_key)
        )

    @override
    async def list_by_issue(self, issue_id: uuid.UUID) -> list[Comment]:
        """Read comments chronologically in one query, without metadata-route eager loads."""
        result = await self.db.scalars(
            select(Comment)
            .options(joinedload(Comment.author))
            .where(Comment.issue_id == issue_id, Comment.reply_to.is_(None), ~Comment.pull_request_comment.has())
            .order_by(Comment.created_at, Comment.id)
        )
        return list(result.all())
