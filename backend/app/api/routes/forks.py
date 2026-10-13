"""Repository fork routes."""

from __future__ import annotations

from fastapi import APIRouter, Response

from app.api.dependencies import AuthorizationServiceDep, CurrentUser, ForkServiceDep, OptionalUser
from app.api.permissions import require_permission
from app.schemas.social import ForkCreate, ForkPublic, ForksPublic

router = APIRouter(prefix="/repositories", tags=["forks"])


@router.get("/{owner}/{repo}/forks")
@require_permission("repository:read", authorization="_authorization", response="_response")
async def list_forks(
    owner: str,
    repo: str,
    fork_service: ForkServiceDep,
    current_user: OptionalUser,
    offset: int = 0,
    limit: int = 100,
    *,
    _authorization: AuthorizationServiceDep,
    _response: Response,
) -> ForksPublic:
    """List forks of a repository."""
    return await fork_service.list_forks(owner, repo, offset, limit, current_user)


@router.post("/{owner}/{repo}/forks", status_code=201)
@require_permission("repository:read", authorization="_authorization", response="_response")
async def fork_repository(
    owner: str,
    repo: str,
    body: ForkCreate,
    fork_service: ForkServiceDep,
    current_user: CurrentUser,
    *,
    _authorization: AuthorizationServiceDep,
    _response: Response,
) -> ForkPublic:
    """Fork a repository."""
    return await fork_service.fork(owner, repo, body, current_user)
