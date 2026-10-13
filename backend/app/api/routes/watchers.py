"""Repository watcher routes."""

from __future__ import annotations

from fastapi import APIRouter, Response

from app.api.dependencies import AuthorizationServiceDep, CurrentUser, OptionalUser, WatcherServiceDep
from app.api.permissions import require_permission
from app.schemas.social import WatchersPublic, WatcherState

router = APIRouter(prefix="/repositories", tags=["watchers"])


@router.get("/{owner}/{repo}/watch")
@require_permission("repository:read", authorization="_authorization", response="_response")
async def get_watch_state(
    owner: str,
    repo: str,
    watcher_service: WatcherServiceDep,
    current_user: CurrentUser,
    *,
    _authorization: AuthorizationServiceDep,
    _response: Response,
) -> WatcherState:
    """Get the current user's watch state for a repository."""
    return await watcher_service.state(owner, repo, current_user)


@router.put("/{owner}/{repo}/watch")
@require_permission("repository:read", authorization="_authorization", response="_response")
async def watch_repository(
    owner: str,
    repo: str,
    watcher_service: WatcherServiceDep,
    current_user: CurrentUser,
    *,
    _authorization: AuthorizationServiceDep,
    _response: Response,
) -> WatcherState:
    """Watch a repository."""
    return await watcher_service.watch(owner, repo, current_user)


@router.delete("/{owner}/{repo}/watch")
@require_permission("repository:read", authorization="_authorization", response="_response")
async def unwatch_repository(
    owner: str,
    repo: str,
    watcher_service: WatcherServiceDep,
    current_user: CurrentUser,
    *,
    _authorization: AuthorizationServiceDep,
    _response: Response,
) -> WatcherState:
    """Stop watching a repository."""
    return await watcher_service.unwatch(owner, repo, current_user)


@router.get("/{owner}/{repo}/watchers")
@require_permission("repository:read", authorization="_authorization", user="_current_user", response="_response")
async def list_watchers(
    owner: str,
    repo: str,
    watcher_service: WatcherServiceDep,
    offset: int = 0,
    limit: int = 100,
    *,
    _authorization: AuthorizationServiceDep,
    _current_user: OptionalUser,
    _response: Response,
) -> WatchersPublic:
    """List users watching a repository."""
    return await watcher_service.watchers(owner, repo, offset, limit)
