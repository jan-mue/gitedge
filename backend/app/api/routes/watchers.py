"""Repository watcher routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.dependencies import CurrentUser, OptionalUser, WatcherServiceDep
from app.api.permissions import require_permission
from app.entities.users import User
from app.schemas.social import WatchersPublic, WatcherState

router = APIRouter(prefix="/repositories", tags=["watchers"])


@router.get("/{owner}/{repo}/watch")
async def get_watch_state(
    owner: str,
    repo: str,
    watcher_service: WatcherServiceDep,
    current_user: Annotated[User, Depends(require_permission("repository:read", user_dep=CurrentUser))],
) -> WatcherState:
    """Get the current user's watch state for a repository."""
    return await watcher_service.state(owner, repo, current_user)


@router.put("/{owner}/{repo}/watch")
async def watch_repository(
    owner: str,
    repo: str,
    watcher_service: WatcherServiceDep,
    current_user: Annotated[User, Depends(require_permission("repository:read", user_dep=CurrentUser))],
) -> WatcherState:
    """Watch a repository."""
    return await watcher_service.watch(owner, repo, current_user)


@router.delete("/{owner}/{repo}/watch")
async def unwatch_repository(
    owner: str,
    repo: str,
    watcher_service: WatcherServiceDep,
    current_user: Annotated[User, Depends(require_permission("repository:read", user_dep=CurrentUser))],
) -> WatcherState:
    """Stop watching a repository."""
    return await watcher_service.unwatch(owner, repo, current_user)


@router.get(
    "/{owner}/{repo}/watchers", dependencies=[Depends(require_permission("repository:read", user_dep=OptionalUser))]
)
async def list_watchers(
    owner: str,
    repo: str,
    watcher_service: WatcherServiceDep,
    offset: int = 0,
    limit: int = 100,
) -> WatchersPublic:
    """List users watching a repository."""
    return await watcher_service.watchers(owner, repo, offset, limit)
