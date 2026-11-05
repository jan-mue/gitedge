"""Authenticated notification center and delivery preference endpoints."""

import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Query

from app.api.dependencies import CurrentUser, NotificationServiceDep
from app.schemas.notifications import (
    NotificationPreferences,
    NotificationPreferencesPublic,
    NotificationsPublic,
    NotificationUpdate,
    RepositoryNotificationPreferences,
)

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("/")
async def list_notifications(
    current_user: CurrentUser,
    service: NotificationServiceDep,
    view: Literal["inbox", "archived"] = "inbox",
    read: Literal["all", "unread"] = "all",
    reason: str = "",
    repo: str = "",
    query: Annotated[str, Query(max_length=255)] = "",
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    focus: uuid.UUID | None = None,
) -> NotificationsPublic:
    """List the current user's notifications, with unread and filter counts."""
    return await service.list_notifications(
        current_user,
        view=view,
        read=read,
        reason=reason,
        repo=repo,
        query=query,
        offset=offset,
        limit=limit,
        focus=focus,
    )


@router.patch("/", status_code=204)
async def update_notifications(
    body: NotificationUpdate, current_user: CurrentUser, service: NotificationServiceDep
) -> None:
    """Read, archive, restore, or unsubscribe from selected notifications."""
    await service.update(current_user, body)


@router.get("/preferences")
async def get_preferences(current_user: CurrentUser, service: NotificationServiceDep) -> NotificationPreferencesPublic:
    """Read email versus notification center delivery preferences."""
    return await service.preferences(current_user)


@router.put("/preferences")
async def set_preferences(
    body: NotificationPreferences, current_user: CurrentUser, service: NotificationServiceDep
) -> NotificationPreferencesPublic:
    """Opt in to email in addition to the notification center."""
    return await service.set_preferences(current_user, email=body.email)


@router.get("/repositories/{owner}/{repo}")
async def get_repository_preferences(
    owner: str, repo: str, current_user: CurrentUser, service: NotificationServiceDep
) -> RepositoryNotificationPreferences:
    """Read this user's repository notification categories."""
    return await service.repository_preferences(current_user, owner, repo)


@router.put("/repositories/{owner}/{repo}")
async def set_repository_preferences(
    owner: str,
    repo: str,
    body: RepositoryNotificationPreferences,
    current_user: CurrentUser,
    service: NotificationServiceDep,
) -> RepositoryNotificationPreferences:
    """Save this user's repository notification categories."""
    return await service.set_repository_preferences(current_user, owner, repo, body)


@router.post("/read-all", status_code=204)
async def mark_all_read(current_user: CurrentUser, service: NotificationServiceDep) -> None:
    """Mark the entire inbox read."""
    await service.mark_all_read(current_user)


@router.post("/repositories/{owner}/{repo}/archive", status_code=204)
async def archive_repository(owner: str, repo: str, current_user: CurrentUser, service: NotificationServiceDep) -> None:
    """Dismiss all notifications for one repository."""
    await service.archive_repository(current_user, owner, repo)
