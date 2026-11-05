"""Comment store for database operations."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, override

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import joinedload, selectinload

from app.clients.database import CrudStore, SQLStore
from app.entities.comments import Comment
from app.entities.issues import Issue
from app.entities.reactions import CommentReaction
from app.entities.repositories import Repository
from app.exceptions import NotFoundError, RepositoryNotFoundError

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
    async def context(self, comment: Comment) -> tuple[Issue, Repository]:
        """Load the discussion and repository, including the owner needed for links."""
        issue = await self.db.scalar(select(Issue).where(Issue.id == comment.issue_id))
        if issue is None:
            raise NotFoundError("Discussion not found")
        repo = await self.db.scalar(
            select(Repository).options(selectinload(Repository.owner)).where(Repository.id == issue.repo_id)
        )
        if repo is None:
            raise RepositoryNotFoundError
        return issue, repo

    @override
    async def reactions(self, comment_id: uuid.UUID) -> list[CommentReaction]:
        """Read the comment's reaction counts."""
        rows = await self.db.scalars(select(CommentReaction).where(CommentReaction.comment_id == comment_id))
        return list(rows.all())

    @override
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
