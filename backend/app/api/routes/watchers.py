"""Repository watcher routes."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.dependencies import CurrentUser, WatcherServiceDep
from app.schemas.social import WatchersPublic, WatcherState

router = APIRouter(prefix="/repositories", tags=["watchers"])


@router.get("/{path:path}/watch")
async def get_watch_state(path: str, watcher_service: WatcherServiceDep, current_user: CurrentUser) -> WatcherState:
    """Get the current user's watch state for a repository."""
    return await watcher_service.state(path, current_user)


@router.put("/{path:path}/watch")
async def watch_repository(path: str, watcher_service: WatcherServiceDep, current_user: CurrentUser) -> WatcherState:
    """Watch a repository."""
    return await watcher_service.watch(path, current_user)


@router.delete("/{path:path}/watch")
async def unwatch_repository(path: str, watcher_service: WatcherServiceDep, current_user: CurrentUser) -> WatcherState:
    """Stop watching a repository."""
    return await watcher_service.unwatch(path, current_user)


@router.get("/{path:path}/watchers")
async def list_watchers(
    path: str, watcher_service: WatcherServiceDep, offset: int = 0, limit: int = 100
) -> WatchersPublic:
    """List users watching a repository."""
    return await watcher_service.watchers(path, offset, limit)
