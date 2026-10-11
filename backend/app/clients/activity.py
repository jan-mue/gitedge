"""Activity store for database operations."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from sqlalchemy import func, or_, select, tuple_
from sqlalchemy.orm import selectinload

from app.clients.database import CrudStore, SQLStore
from app.entities.activity import Activity, ActivityTargetType
from app.entities.comments import Comment
from app.entities.issues import Issue
from app.entities.repositories import Repository
from app.entities.stars import Star
from app.schemas.activity import ActivityTargetPreview

if TYPE_CHECKING:
    import uuid
    from datetime import datetime

    from sqlalchemy.ext.asyncio import AsyncSession

_ACTIVITY_OPTIONS = (
    selectinload(Activity.actor),
    selectinload(Activity.repo).selectinload(Repository.owner),
)
_PREVIEW_LENGTH = 4000


class ActivityStore(CrudStore[Activity], ABC):
    """Abstract activity store with activity-specific queries."""

    @abstractmethod
    async def get_target_previews(self, activities: list[Activity]) -> dict[uuid.UUID, ActivityTargetPreview]:
        """Get issue and pull request previews for one feed page in a batch."""

    @abstractmethod
    async def list_feed(self, user_id: uuid.UUID, offset: int = 0, limit: int = 50) -> list[Activity]:
        """List events from owned and starred repositories without loading those repositories."""

    @abstractmethod
    async def list_in_period(self, repo_id: uuid.UUID, start: datetime, end: datetime) -> list[Activity]:
        """List all repository events within a period, without feed pagination."""

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

    async def list_in_period(self, repo_id: uuid.UUID, start: datetime, end: datetime) -> list[Activity]:
        """List repository events in the inclusive period, newest first."""
        result = await self.db.scalars(
            select(Activity)
            .options(*_ACTIVITY_OPTIONS)
            .where(Activity.repo_id == repo_id, Activity.created_at >= start, Activity.created_at <= end)
            .order_by(Activity.created_at.desc(), Activity.id.desc())
        )
        return list(result.all())

    async def list_recent(self, offset: int = 0, limit: int = 50) -> list[Activity]:
        """List recent activity across all repositories, newest first."""
        result = await self.db.scalars(
            select(Activity)
            .options(*_ACTIVITY_OPTIONS)
            .order_by(Activity.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(result.all())

    async def list_feed(self, user_id: uuid.UUID, offset: int = 0, limit: int = 50) -> list[Activity]:
        """Select a personalized feed page using ownership and star subqueries.

        Args:
            user_id: Authenticated user.
            offset: Number of events to skip.
            limit: Maximum number of events.

        Returns:
            Events with actor and repository metadata loaded.
        """
        owned = select(Repository.id).where(Repository.owner_id == user_id)
        starred = select(Star.repo_id).where(Star.user_id == user_id)
        result = await self.db.scalars(
            select(Activity)
            .options(*_ACTIVITY_OPTIONS)
            .where(or_(Activity.repo_id.in_(owned), Activity.repo_id.in_(starred)))
            .order_by(Activity.created_at.desc(), Activity.id.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(result.all())

    async def get_target_previews(self, activities: list[Activity]) -> dict[uuid.UUID, ActivityTargetPreview]:
        """Read bounded descriptions, states, and comment counts in one metadata query."""
        targets = {
            (activity.repo_id, activity.target_number)
            for activity in activities
            if activity.repo_id is not None
            and activity.target_number is not None
            and activity.target_type in (ActivityTargetType.ISSUE, ActivityTargetType.PULL_REQUEST)
        }
        if not targets:
            return {}
        comments = select(func.count()).where(Comment.issue_id == Issue.id).correlate(Issue).scalar_subquery()
        rows = await self.db.execute(
            select(
                Issue.repo_id,
                Issue.number,
                Issue.kind,
                func.substr(Issue.body, 1, _PREVIEW_LENGTH),
                Issue.state,
                comments,
                func.length(Issue.body),
            ).where(tuple_(Issue.repo_id, Issue.number).in_(targets))
        )
        previews = {
            (repo_id, number, kind): ActivityTargetPreview(
                body=body, body_truncated=(length or 0) > _PREVIEW_LENGTH, state=state, comments_count=count
            )
            for repo_id, number, kind, body, state, count, length in rows
        }
        return {
            activity.id: preview
            for activity in activities
            if (preview := previews.get((activity.repo_id, activity.target_number, activity.target_type))) is not None
        }

    async def list_by_repo(self, repo_id: uuid.UUID, offset: int = 0, limit: int = 50) -> list[Activity]:
        """List activity for a repository, newest first."""
        result = await self.db.scalars(
            select(Activity)
            .options(*_ACTIVITY_OPTIONS)
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
            .options(*_ACTIVITY_OPTIONS)
            .where(Activity.repo_id.in_(repo_ids))
            .order_by(Activity.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(result.all())
