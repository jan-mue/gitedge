"""Database operations for reviews and private draft workspaces."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, override

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import joinedload, selectinload

from app.entities.comments import Comment
from app.entities.reviews import PullRequestComment, PullRequestReview, PullRequestReviewWorkspace

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession


class ReviewStore(ABC):
    """Persistence boundary for pull request reviews."""

    @abstractmethod
    async def get_review(self, pull_request_id: uuid.UUID, review_id: uuid.UUID) -> PullRequestReview | None:
        """Find a published review within this pull request."""

    @abstractmethod
    async def add_reply(self, reply: Comment) -> None:
        """Persist a reply without changing the original review."""

    @abstractmethod
    async def list_reviews(self, pull_request_id: uuid.UUID) -> list[PullRequestReview]:
        """Load submitted reviews with their authors."""

    @abstractmethod
    async def workspace(
        self, pull_request_id: uuid.UUID, author_id: uuid.UUID, *, for_update: bool = False
    ) -> PullRequestReviewWorkspace:
        """Load or initialize a private workspace."""

    @abstractmethod
    async def save_workspace(self, workspace: PullRequestReviewWorkspace) -> None:
        """Save the private workspace."""

    @abstractmethod
    async def submit(self, review: PullRequestReview, workspace: PullRequestReviewWorkspace) -> None:
        """Save a submitted review and clear its private draft atomically."""


class SQLReviewStore(ReviewStore):
    """SQLAlchemy review persistence."""

    def __init__(self, db: AsyncSession) -> None:
        """Initialize with the request's database session."""
        self.db = db

    @override
    async def list_reviews(self, pull_request_id: uuid.UUID) -> list[PullRequestReview]:
        """Load submitted reviews in chronological order."""
        result = await self.db.scalars(
            select(PullRequestReview)
            .options(
                joinedload(PullRequestReview.author),
                selectinload(PullRequestReview.comments)
                .joinedload(PullRequestComment.comment)
                .options(joinedload(Comment.author), selectinload(Comment.replies).joinedload(Comment.author)),
            )
            .where(PullRequestReview.pull_request_id == pull_request_id)
            .order_by(PullRequestReview.created_at, PullRequestReview.id)
        )
        return list(result.all())

    @override
    async def get_review(self, pull_request_id: uuid.UUID, review_id: uuid.UUID) -> PullRequestReview | None:
        """Scope lookups so reviews cannot be addressed through another PR."""
        return await self.db.scalar(
            select(PullRequestReview)
            .options(
                selectinload(PullRequestReview.comments)
                .joinedload(PullRequestComment.comment)
                .options(joinedload(Comment.author), selectinload(Comment.replies).joinedload(Comment.author))
            )
            .where(PullRequestReview.id == review_id, PullRequestReview.pull_request_id == pull_request_id)
        )

    @override
    async def add_reply(self, reply: Comment) -> None:
        """Save the reply and load server-generated dates."""
        self.db.add(reply)
        await self.db.commit()
        await self.db.refresh(reply, attribute_names=["id", "created_at", "updated_at"])

    @override
    async def workspace(
        self, pull_request_id: uuid.UUID, author_id: uuid.UUID, *, for_update: bool = False
    ) -> PullRequestReviewWorkspace:
        """Load a workspace without creating rows on a read request."""
        if for_update:
            await self.db.execute(
                insert(PullRequestReviewWorkspace)
                .values(pull_request_id=pull_request_id, author_id=author_id, reviewed_paths=[])
                .on_conflict_do_nothing(index_elements=["pull_request_id", "author_id"])
            )
        statement = select(PullRequestReviewWorkspace).where(
            PullRequestReviewWorkspace.pull_request_id == pull_request_id,
            PullRequestReviewWorkspace.author_id == author_id,
        )
        if for_update:
            statement = statement.with_for_update()
        workspace = await self.db.scalar(statement)
        return workspace or PullRequestReviewWorkspace(
            pull_request_id=pull_request_id, author_id=author_id, reviewed_paths=[]
        )

    async def _save_workspace(self, workspace: PullRequestReviewWorkspace) -> None:
        values = {
            "pull_request_id": workspace.pull_request_id,
            "author_id": workspace.author_id,
            "draft": workspace.draft,
            "base_commit": workspace.base_commit,
            "head_commit": workspace.head_commit,
            "reviewed_paths": workspace.reviewed_paths,
        }
        statement = insert(PullRequestReviewWorkspace).values(**values)
        await self.db.execute(
            statement.on_conflict_do_update(index_elements=["pull_request_id", "author_id"], set_=values)
        )

    @override
    async def save_workspace(self, workspace: PullRequestReviewWorkspace) -> None:
        """Upsert a user's workspace."""
        await self._save_workspace(workspace)
        await self.db.commit()

    @override
    async def submit(self, review: PullRequestReview, workspace: PullRequestReviewWorkspace) -> None:
        """Persist a review and remove its draft in one transaction."""
        self.db.add(review)
        workspace.draft = None
        await self._save_workspace(workspace)
        await self.db.commit()
        await self.db.refresh(review, attribute_names=["id", "created_at", "updated_at"])
