"""Activity feed routes."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.dependencies import ActivityServiceDep, CurrentUser
from app.schemas.activity import ActivitiesPublic

router = APIRouter(prefix="/repositories", tags=["activity"])
user_router = APIRouter(prefix="/users", tags=["activity"])


@router.get("/{owner}/{repo}/activity")
async def get_repository_activity(
    owner: str, repo: str, activity_service: ActivityServiceDep, offset: int = 0, limit: int = 50
) -> ActivitiesPublic:
    """List activity for a repository."""
    return await activity_service.repo_activity(owner, repo, offset, limit)


@user_router.get("/me/feed")
async def get_feed(
    activity_service: ActivityServiceDep, current_user: CurrentUser, offset: int = 0, limit: int = 50
) -> ActivitiesPublic:
    """Get the current user's activity feed."""
    return await activity_service.feed(current_user, offset, limit)
