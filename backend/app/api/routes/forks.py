"""Repository fork routes."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.dependencies import CurrentUser, ForkServiceDep
from app.schemas.social import ForkCreate, ForkPublic, ForksPublic

router = APIRouter(prefix="/repositories", tags=["forks"])


@router.get("/{path:path}/forks")
async def list_forks(path: str, fork_service: ForkServiceDep, offset: int = 0, limit: int = 100) -> ForksPublic:
    """List forks of a repository."""
    return await fork_service.list_forks(path, offset, limit)


@router.post("/{path:path}/forks", status_code=201)
async def fork_repository(
    path: str, body: ForkCreate, fork_service: ForkServiceDep, current_user: CurrentUser
) -> ForkPublic:
    """Fork a repository."""
    return await fork_service.fork(path, body, current_user)
