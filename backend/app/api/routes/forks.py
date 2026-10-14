"""Repository fork routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.dependencies import CurrentUser, ForkServiceDep, OptionalUser
from app.api.permissions import require_permission
from app.entities.users import User
from app.schemas.social import ForkCreate, ForkPublic, ForksPublic

router = APIRouter(prefix="/repositories", tags=["forks"])


@router.get("/{owner}/{repo}/forks")
async def list_forks(
    owner: str,
    repo: str,
    fork_service: ForkServiceDep,
    current_user: Annotated[User | None, Depends(require_permission("repository:read", user_dep=OptionalUser))],
    offset: int = 0,
    limit: int = 100,
) -> ForksPublic:
    """List forks of a repository."""
    return await fork_service.list_forks(owner, repo, offset, limit, current_user)


@router.post("/{owner}/{repo}/forks", status_code=201)
async def fork_repository(
    owner: str,
    repo: str,
    body: ForkCreate,
    fork_service: ForkServiceDep,
    current_user: Annotated[User, Depends(require_permission("repository:read", user_dep=CurrentUser))],
) -> ForkPublic:
    """Fork a repository."""
    return await fork_service.fork(owner, repo, body, current_user)
