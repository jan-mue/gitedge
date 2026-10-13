"""Repository fork routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.dependencies import CurrentUser, ForkServiceDep, OptionalUser, require_repository
from app.schemas.social import ForkCreate, ForkPublic, ForksPublic

router = APIRouter(prefix="/repositories", tags=["forks"])


@router.get("/{owner}/{repo}/forks", dependencies=[Depends(require_repository("repository:read"))])
async def list_forks(
    owner: str, repo: str, fork_service: ForkServiceDep, user: OptionalUser, offset: int = 0, limit: int = 100
) -> ForksPublic:
    """List forks of a repository."""
    return await fork_service.list_forks(owner, repo, offset, limit, user)


@router.post("/{owner}/{repo}/forks", status_code=201, dependencies=[Depends(require_repository("repository:read"))])
async def fork_repository(
    owner: str, repo: str, body: ForkCreate, fork_service: ForkServiceDep, current_user: CurrentUser
) -> ForkPublic:
    """Fork a repository."""
    return await fork_service.fork(owner, repo, body, current_user)
