"""Comment store for database operations."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import selectinload

from app.clients.database import CrudStore, SQLStore
from app.entities.comments import Comment
from app.entities.issues import Issue
from app.entities.reactions import CommentReaction
from app.entities.repositories import Repository
from app.exceptions import NotFoundError

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession


class CommentStore(CrudStore[Comment], ABC):
    """Abstract comment store."""

    @abstractmethod
    async def context(self, comment: Comment) -> tuple[Issue, Repository]:
        """Load a comment's discussion and repository."""

    @abstractmethod
    async def reactions(self, comment_id: uuid.UUID) -> list[CommentReaction]:
        """Read persistent reactions for a comment."""

    @abstractmethod
    async def set_reaction(self, comment_id: uuid.UUID, user_id: uuid.UUID, emoji: str, *, enabled: bool) -> bool:
        """Set a reaction idempotently, returning whether it was newly added."""


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

    async def context(self, comment: Comment) -> tuple[Issue, Repository]:
        """Load the discussion and repository, including the owner needed for links."""
        issue = await self.db.scalar(select(Issue).where(Issue.id == comment.issue_id))
        if issue is None:
            raise NotFoundError("Discussion not found")
        repo = await self.db.scalar(
            select(Repository).options(selectinload(Repository.owner)).where(Repository.id == issue.repo_id)
        )
        if repo is None:
            raise NotFoundError("Repository not found")
        return issue, repo

    async def reactions(self, comment_id: uuid.UUID) -> list[CommentReaction]:
        """Read the comment's reaction counts."""
        rows = await self.db.scalars(select(CommentReaction).where(CommentReaction.comment_id == comment_id))
        return list(rows.all())

    async def set_reaction(self, comment_id: uuid.UUID, user_id: uuid.UUID, emoji: str, *, enabled: bool) -> bool:
        """Use the unique constraint to make repeated requests safe."""
        added = False
        if enabled:
            result = await self.db.scalar(
                insert(CommentReaction)
                .values(comment_id=comment_id, user_id=user_id, emoji=emoji)
                .on_conflict_do_nothing(index_elements=["comment_id", "user_id", "emoji"])
                .returning(CommentReaction.id)
            )
            added = result is not None
        else:
            await self.db.execute(
                delete(CommentReaction).where(
                    CommentReaction.comment_id == comment_id,
                    CommentReaction.user_id == user_id,
                    CommentReaction.emoji == emoji,
                )
            )
        await self.db.commit()
        return added
