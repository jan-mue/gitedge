"""Data access for notification recipients, inbox state, and preferences."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING

from sqlalchemy import String, cast, func, literal, or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import selectinload

from app.clients.database import CrudStore, SQLStore
from app.entities.activity import Activity
from app.entities.comments import Comment
from app.entities.issues import Issue
from app.entities.notifications import (
    Notification,
    NotificationPreference,
    NotificationRepositoryPreference,
    NotificationSubscription,
)
from app.entities.principals import Principal
from app.entities.repositories import Repository
from app.entities.users import User
from app.entities.watchers import Watcher
from app.schemas.notifications import NOTIFICATION_CATEGORIES, NotificationFilter

if TYPE_CHECKING:
    import uuid
    from typing import Any

    from sqlalchemy import Select
    from sqlalchemy.ext.asyncio import AsyncSession


_NOTIFICATION_OPTIONS = (
    selectinload(Notification.activity).selectinload(Activity.actor),
    selectinload(Notification.activity).selectinload(Activity.repo).selectinload(Repository.owner),
)


def notification_thread(activity: Activity) -> str:
    """Use the same key for every event in a discussion."""
    return f"{activity.target_type or 'repository'}:{activity.target_number or 0}"


@dataclass
class NotificationPage:
    """A bounded inbox page and aggregate navigation counts."""

    entries: list[Notification]
    count: int
    unread_count: int
    inbox_count: int
    archived_count: int
    repository_counts: dict[str, int]
    reasons: dict[str, int]


class NotificationStore(CrudStore[Notification], ABC):
    """Notification-specific persistence operations."""

    @abstractmethod
    async def audience(self, activity: Activity, mentions: set[str]) -> list[tuple[User, str]]:
        """Find owners, watchers, discussion participants, and explicit mentions."""

    @abstractmethod
    async def list_for_user(self, user: User, ids: list[uuid.UUID] | None = None) -> list[Notification]:
        """Load only the recipient's accessible notifications and destinations."""

    @abstractmethod
    async def page(self, user: User, filters: NotificationFilter) -> NotificationPage:
        """Read one filtered page and aggregate counts without loading history."""

    @abstractmethod
    async def mark_all_read(self, user: User) -> None:
        """Mark all accessible inbox entries read in one operation."""

    @abstractmethod
    async def archive_repository(self, user: User, repo_id: uuid.UUID) -> None:
        """Archive the recipient's entries for an accessible repository."""

    @abstractmethod
    async def email_enabled(self, user_id: uuid.UUID) -> bool:
        """Read the account's email opt-in."""

    @abstractmethod
    async def set_email(self, user_id: uuid.UUID, enabled: bool) -> None:
        """Persist the account's email opt-in."""

    @abstractmethod
    async def categories(self, user_id: uuid.UUID, repo_id: uuid.UUID) -> list[str]:
        """Read the repository's enabled categories."""

    @abstractmethod
    async def set_categories(self, user_id: uuid.UUID, repo_id: uuid.UUID, categories: list[str]) -> None:
        """Persist repository category preferences."""

    @abstractmethod
    async def muted_threads(self, user_id: uuid.UUID) -> set[tuple[uuid.UUID, str]]:
        """Read muted discussion keys in a batch."""

    @abstractmethod
    async def set_muted(self, user_id: uuid.UUID, activity: Activity, muted: bool) -> None:
        """Persist an explicit subscription state."""


class SQLNotificationStore(NotificationStore, SQLStore[Notification]):
    """SQLAlchemy implementation of inbox persistence."""

    def __init__(self, db: AsyncSession) -> None:
        """Bind the store to the request session."""
        super().__init__(db, Notification)

    async def audience(self, activity: Activity, mentions: set[str]) -> list[tuple[User, str]]:
        """Resolve recipients without broadcasting private repository activity."""
        repo = await self.db.get(Repository, activity.repo_id)
        if repo is None:
            return []
        reasons = {repo.owner_id: "subscribed"}
        watchers = await self.db.scalars(select(Watcher.user_id).where(Watcher.repo_id == repo.id))
        reasons.update(dict.fromkeys(watchers.all(), "subscribed"))
        subscribed = await self.db.scalars(
            select(NotificationSubscription.user_id).where(
                NotificationSubscription.repo_id == repo.id,
                NotificationSubscription.thread == notification_thread(activity),
                NotificationSubscription.muted.is_(False),
            )
        )
        reasons.update(dict.fromkeys(subscribed.all(), "participating"))
        issue = (
            await self.db.scalar(select(Issue).where(Issue.repo_id == repo.id, Issue.number == activity.target_number))
            if activity.target_number is not None
            else None
        )
        if issue is not None:
            participants = await self.db.scalars(select(Comment.author_id).where(Comment.issue_id == issue.id))
            reasons.update(dict.fromkeys(participants.all(), "participating"))
            reasons[issue.author_id] = "author"
        if activity.comment_id is not None and activity.kind == "reaction":
            comment = await self.db.get(Comment, activity.comment_id)
            if comment is not None:
                reasons[comment.author_id] = "reaction"
        mentioned = await self.db.scalars(select(User.id).where(User.lower_name.in_(mentions)))
        reasons.update(dict.fromkeys(mentioned.all(), "mentioned"))
        users = await self.db.scalars(select(User).where(User.id.in_(reasons), User.is_active.is_(True)))
        return [
            (user, reasons[user.id])
            for user in users
            if user.id != activity.actor_id and (not repo.is_private or user.id == repo.owner_id or user.is_superuser)
        ]

    @staticmethod
    def _inbox_query(user: User) -> Select[Notification]:
        """Scope every inbox query to the recipient and currently visible repositories."""
        return (
            select(Notification)
            .join(Activity, Notification.activity_id == Activity.id)
            .join(Repository, Activity.repo_id == Repository.id)
            .join(Principal, Repository.owner_id == Principal.id)
            .where(
                Notification.user_id == user.id,
                or_(Repository.is_private.is_(False), Repository.owner_id == user.id, literal(user.is_superuser)),
            )
        )

    async def list_for_user(self, user: User, ids: list[uuid.UUID] | None = None) -> list[Notification]:
        """Read selected accessible rows for ownership checks."""
        query = self._inbox_query(user)
        if ids is not None:
            query = query.where(Notification.id.in_(ids))
        result = await self.db.scalars(
            query.options(*_NOTIFICATION_OPTIONS).order_by(Notification.created_at.desc(), Notification.id.desc())
        )
        return list(result.all())

    async def page(self, user: User, filters: NotificationFilter) -> NotificationPage:
        """Paginate in SQL and compute counts separately from destination hydration."""
        base = self._inbox_query(user)
        repository_name = Principal.name + "/" + Repository.name
        aggregates = await self.db.execute(
            base.with_only_columns(
                Notification.is_archived,
                Notification.is_read,
                repository_name,
                Notification.reason,
                func.count(),
                maintain_column_froms=True,
            ).group_by(Notification.is_archived, Notification.is_read, repository_name, Notification.reason)
        )
        inbox_count = archived_count = unread_count = 0
        repositories: dict[str, int] = {}
        reasons: dict[str, int] = {}
        archived_view = filters.view == "archived"
        for archived, read, repository, reason, count in aggregates:
            if archived:
                archived_count += count
            else:
                inbox_count += count
                if not read:
                    unread_count += count
            if archived == archived_view:
                repositories[repository] = repositories.get(repository, 0) + count
                reasons[reason] = reasons.get(reason, 0) + count
        query = base.where(Notification.is_archived.is_(archived_view))
        if filters.read == "unread":
            query = query.where(or_(Notification.is_read.is_(False), Notification.id == filters.focus))
        if filters.reason:
            query = query.where(Notification.reason == filters.reason)
        if filters.repo:
            query = query.where(repository_name == filters.repo)
        if filters.query.strip():
            text = func.lower(
                func.concat(Activity.title, " ", repository_name, " ", cast(Activity.target_number, String))
            )
            query = query.where(text.contains(filters.query.strip().lower(), autoescape=True))
        count = await self.db.scalar(query.with_only_columns(func.count(), maintain_column_froms=True))
        result = await self.db.scalars(
            query.options(*_NOTIFICATION_OPTIONS)
            .order_by(Notification.created_at.desc(), Notification.id.desc())
            .offset(filters.offset)
            .limit(filters.limit)
        )
        return NotificationPage(
            list(result.all()), count or 0, unread_count, inbox_count, archived_count, repositories, reasons
        )

    async def mark_all_read(self, user: User) -> None:
        """Update all visible inbox rows without loading them."""
        ids = self._inbox_query(user).with_only_columns(Notification.id).where(Notification.is_archived.is_(False))
        await self.db.execute(update(Notification).where(Notification.id.in_(ids)).values(is_read=True))
        await self.db.commit()

    async def archive_repository(self, user: User, repo_id: uuid.UUID) -> None:
        """Archive every accessible notification for this repository in one statement."""
        ids = self._inbox_query(user).with_only_columns(Notification.id).where(Activity.repo_id == repo_id)
        await self.db.execute(
            update(Notification).where(Notification.id.in_(ids)).values(is_read=True, is_archived=True)
        )
        await self.db.commit()

    async def email_enabled(self, user_id: uuid.UUID) -> bool:
        """Default new accounts to notification center only."""
        return bool(
            await self.db.scalar(select(NotificationPreference.email).where(NotificationPreference.user_id == user_id))
        )

    async def _upsert(self, entity: type, values: dict[str, Any], keys: list[str], changes: dict[str, Any]) -> None:
        """Persist a preference atomically under concurrent requests."""
        await self.db.execute(insert(entity).values(**values).on_conflict_do_update(index_elements=keys, set_=changes))
        await self.db.commit()

    async def set_email(self, user_id: uuid.UUID, enabled: bool) -> None:
        """Persist the delivery channel."""
        await self._upsert(
            NotificationPreference, {"user_id": user_id, "email": enabled}, ["user_id"], {"email": enabled}
        )

    async def categories(self, user_id: uuid.UUID, repo_id: uuid.UUID) -> list[str]:
        """Read repository preferences, enabling every category by default."""
        categories = await self.db.scalar(
            select(NotificationRepositoryPreference.categories).where(
                NotificationRepositoryPreference.user_id == user_id, NotificationRepositoryPreference.repo_id == repo_id
            )
        )
        return list(NOTIFICATION_CATEGORIES) if categories is None else categories

    async def set_categories(self, user_id: uuid.UUID, repo_id: uuid.UUID, categories: list[str]) -> None:
        """Save repository preferences."""
        await self._upsert(
            NotificationRepositoryPreference,
            {"user_id": user_id, "repo_id": repo_id, "categories": categories},
            ["user_id", "repo_id"],
            {"categories": categories},
        )

    async def muted_threads(self, user_id: uuid.UUID) -> set[tuple[uuid.UUID, str]]:
        """Get discussion subscriptions in one query."""
        rows = await self.db.execute(
            select(NotificationSubscription.repo_id, NotificationSubscription.thread).where(
                NotificationSubscription.user_id == user_id, NotificationSubscription.muted.is_(True)
            )
        )
        return {(repo_id, thread) for repo_id, thread in rows}

    async def set_muted(self, user_id: uuid.UUID, activity: Activity, muted: bool) -> None:
        """Save a thread subscription."""
        await self._upsert(
            NotificationSubscription,
            {"user_id": user_id, "repo_id": activity.repo_id, "thread": notification_thread(activity), "muted": muted},
            ["user_id", "repo_id", "thread"],
            {"muted": muted},
        )
