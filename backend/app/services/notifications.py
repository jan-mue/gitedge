"""Activity delivery and notification center behavior."""

from __future__ import annotations

import logging
import re
from html import escape
from smtplib import SMTPException
from typing import TYPE_CHECKING, Literal, cast
from urllib.parse import quote

from fastapi import HTTPException

from app.clients.notifications import notification_thread
from app.config import settings
from app.entities.notifications import Notification
from app.schemas.notifications import (
    NotificationFilter,
    NotificationPreferencesPublic,
    NotificationPublic,
    NotificationsPublic,
    RepositoryNotificationPreferences,
)

if TYPE_CHECKING:
    import uuid

    from fastapi import BackgroundTasks

    from app.clients.email import EmailClient
    from app.clients.notifications import NotificationStore
    from app.clients.repositories import RepositoryStore
    from app.entities.activity import Activity
    from app.entities.users import User
    from app.schemas.notifications import NotificationCategory, NotificationUpdate

logger = logging.getLogger(__name__)
_MENTION = re.compile(r"(?<![\w@/])@([a-zA-Z0-9][a-zA-Z0-9_-]*)(?![\w-])")


def mentioned_users(text: str) -> set[str]:
    """Find explicit handles, ignoring fenced code, inline code, URLs, and email addresses."""
    text = re.sub(r"```[\s\S]*?```|~~~[\s\S]*?~~~|`[^`\n]*`|https?://\S+", "", text)
    return {name.lower() for name in _MENTION.findall(text)}


def activity_url(activity: Activity) -> str:
    """Build an internal, encoded destination for an activity."""
    repo = activity.repo
    if repo is None:
        raise ValueError("Notification activity requires a repository")
    path = f"/{quote(repo.owner.name, safe='')}/{quote(repo.name, safe='')}"
    if activity.target_type in ("issue", "pull_request") and activity.target_number is not None:
        path += f"/{'pulls' if activity.target_type == 'pull_request' else 'issues'}/{activity.target_number}"
    elif activity.target_type == "release":
        path += "/releases"
    if activity.comment_id is not None:
        path += f"#comment-{activity.comment_id}"
    return path


class NotificationService:
    """Deliver each event once per recipient and persist inbox actions."""

    def __init__(
        self,
        store: NotificationStore,
        repository_store: RepositoryStore,
        email_client: EmailClient,
        background_tasks: BackgroundTasks,
    ) -> None:
        """Bind persistence and the existing SMTP transport."""
        self.store = store
        self.repository_store = repository_store
        self.email_client = email_client
        self.background_tasks = background_tasks

    async def notify(self, activity: Activity, text: str = "", previous_text: str = "") -> None:
        """Deliver to watchers and participants; prioritize new explicit mentions."""
        if activity.repo_id is None:
            return
        mentions = mentioned_users(text) - mentioned_users(previous_text)
        audience = await self.store.audience(activity, mentions)
        for user, reason in audience:
            category: NotificationCategory = (
                "mention"
                if reason == "mentioned"
                else "pull"
                if activity.target_type == "pull_request"
                else "issue"
                if activity.target_type == "issue"
                else "release"
                if activity.target_type == "release"
                else "repository"
            )
            if category not in await self.store.categories(user.id, activity.repo_id):
                continue
            if (activity.repo_id, notification_thread(activity)) in await self.store.muted_threads(user.id):
                continue
            notification = Notification(user_id=user.id, activity_id=activity.id, reason=reason, category=category)
            notification.activity = activity
            await self.store.add(notification)
            if settings.emails_enabled and await self.store.email_enabled(user.id):
                subject, html = self._email_content(activity, notification.id)
                self.background_tasks.add_task(self._send_email, user.email, subject, html, notification.id)

    @staticmethod
    def _email_content(activity: Activity, notification_id: uuid.UUID) -> tuple[str, str]:
        """Snapshot content before the request session closes."""
        url = activity_url(activity)
        path, separator, fragment = url.partition("#")
        url = f"{settings.FRONTEND_HOST.rstrip('/')}{path}?from=notifications&n={notification_id}"
        if separator:
            url += f"#{fragment}"
        repo = activity.repo
        if repo is None:
            raise ValueError("Notification activity requires a repository")
        title = " ".join((activity.title or activity.kind.replace("_", " ")).splitlines())
        subject = f"[{repo.owner.name}/{repo.name}] {title}"
        html = (
            f"<p>{escape(activity.actor.name)}: {escape(activity.kind.replace('_', ' '))}</p>"
            f"<p>{escape(activity.title or '')}</p>"
            f'<p><a href="{escape(url, quote=True)}">View activity</a></p>'
            f'<p><a href="{escape(settings.FRONTEND_HOST.rstrip("/"), quote=True)}/settings?tab=notifications">Notification preferences</a></p>'
        )
        return subject, html

    def _send_email(self, email: str, subject: str, html: str, notification_id: uuid.UUID) -> None:
        """Send after the response, preserving the inbox if SMTP fails."""
        try:
            self.email_client.send_email(email, subject, html)
        except SMTPException, OSError, RuntimeError:
            logger.exception("Notification email delivery failed for notification %s", notification_id)

    async def list_notifications(
        self,
        user: User,
        *,
        view: Literal["inbox", "archived"] = "inbox",
        read: Literal["all", "unread"] = "all",
        reason: str = "",
        repo: str = "",
        query: str = "",
        offset: int = 0,
        limit: int = 50,
        focus: uuid.UUID | None = None,
    ) -> NotificationsPublic:
        """Filter a recipient's inbox and provide navigation counts."""
        page = await self.store.page(
            user,
            NotificationFilter(
                view=view, read=read, reason=reason, repo=repo, query=query, offset=offset, limit=limit, focus=focus
            ),
        )
        muted = await self.store.muted_threads(user.id)
        return NotificationsPublic(
            data=[self._public(n, muted) for n in page.entries],
            count=page.count,
            inbox_count=page.inbox_count,
            archived_count=page.archived_count,
            unread_count=page.unread_count,
            repository_counts=page.repository_counts,
            repositories=sorted(page.repository_counts),
            reasons=page.reasons,
        )

    @staticmethod
    def _public(n: Notification, muted: set[tuple[uuid.UUID, str]]) -> NotificationPublic:
        """Serialize an inbox row with its current destination and subscription."""
        activity = n.activity
        repo = activity.repo
        if repo is None:
            raise ValueError("Notification activity requires a repository")
        return NotificationPublic(
            id=n.id,
            repo_id=repo.id,
            repo=f"{repo.owner.name}/{repo.name}",
            number=activity.target_number,
            title=activity.title or activity.kind.replace("_", " "),
            kind=activity.kind,
            category=cast("NotificationCategory", n.category),
            reason=n.reason,
            actor=activity.actor.name,
            url=activity_url(activity),
            created_at=n.created_at,
            is_read=n.is_read,
            is_archived=n.is_archived,
            unsubscribed=(repo.id, notification_thread(activity)) in muted,
        )

    async def update(self, user: User, body: NotificationUpdate) -> None:
        """Validate ownership of the entire selection before applying any changes."""
        owned = {n.id: n for n in await self.store.list_for_user(user, body.ids)}
        if any(notification_id not in owned for notification_id in body.ids):
            raise HTTPException(status_code=404, detail="Notification not found")
        for notification_id in set(body.ids):
            notification = owned[notification_id]
            if body.is_read is not None:
                notification.is_read = body.is_read
            if body.is_archived is not None:
                notification.is_archived = body.is_archived
                if body.is_archived:
                    notification.is_read = True
            await self.store.update(notification)
            if body.unsubscribed is not None:
                await self.store.set_muted(user.id, notification.activity, body.unsubscribed)

    async def mark_all_read(self, user: User) -> None:
        """Mark every inbox entry read, including entries outside the current page."""
        await self.store.mark_all_read(user)

    async def archive_repository(self, user: User, owner: str, name: str) -> None:
        """Clear every inbox entry for a repository, keeping it restorable."""
        await self.repository_preferences(user, owner, name)
        repository = await self.repository_store.get_by_owner_and_name(owner, name)
        await self.store.archive_repository(user, repository.id)

    async def preferences(self, user: User) -> NotificationPreferencesPublic:
        """Return the account's delivery preference and SMTP availability."""
        return NotificationPreferencesPublic(
            email=await self.store.email_enabled(user.id), email_available=settings.emails_enabled
        )

    async def set_preferences(self, user: User, *, email: bool) -> NotificationPreferencesPublic:
        """Save the recipient's delivery choice."""
        await self.store.set_email(user.id, email)
        return await self.preferences(user)

    async def repository_preferences(self, user: User, owner: str, name: str) -> RepositoryNotificationPreferences:
        """Read category settings after checking repository visibility."""
        repository = await self.repository_store.get_by_owner_and_name(owner, name)
        if repository.is_private and repository.owner_id != user.id and not user.is_superuser:
            raise HTTPException(status_code=404, detail="Repository not found")
        return RepositoryNotificationPreferences.model_validate(
            {"categories": await self.store.categories(user.id, repository.id)}
        )

    async def set_repository_preferences(
        self, user: User, owner: str, name: str, body: RepositoryNotificationPreferences
    ) -> RepositoryNotificationPreferences:
        """Persist repository settings for this recipient only."""
        await self.repository_preferences(user, owner, name)
        repository = await self.repository_store.get_by_owner_and_name(owner, name)
        await self.store.set_categories(user.id, repository.id, list(body.categories))
        return body
