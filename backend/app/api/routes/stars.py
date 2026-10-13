"""Repository star routes."""

from __future__ import annotations

from fastapi import APIRouter, Response

from app.api.dependencies import AuthorizationServiceDep, CurrentUser, OptionalUser, StarServiceDep
from app.api.permissions import require_permission
from app.schemas.repositories import RepositoriesPublic
from app.schemas.social import StargazersPublic, StarState

router = APIRouter(prefix="/repositories", tags=["stars"])
user_router = APIRouter(prefix="/users", tags=["stars"])


@router.get("/{owner}/{repo}/star")
@require_permission("repository:read", authorization="_authorization", response="_response")
async def get_star_state(
    owner: str,
    repo: str,
    star_service: StarServiceDep,
    current_user: CurrentUser,
    *,
    _authorization: AuthorizationServiceDep,
    _response: Response,
) -> StarState:
    """Get the current user's star state for a repository."""
    return await star_service.state(owner, repo, current_user)


@router.put("/{owner}/{repo}/star")
@require_permission("repository:read", authorization="_authorization", response="_response")
async def star_repository(
    owner: str,
    repo: str,
    star_service: StarServiceDep,
    current_user: CurrentUser,
    *,
    _authorization: AuthorizationServiceDep,
    _response: Response,
) -> StarState:
    """Star a repository."""
    return await star_service.star(owner, repo, current_user)


@router.delete("/{owner}/{repo}/star")
@require_permission("repository:read", authorization="_authorization", response="_response")
async def unstar_repository(
    owner: str,
    repo: str,
    star_service: StarServiceDep,
    current_user: CurrentUser,
    *,
    _authorization: AuthorizationServiceDep,
    _response: Response,
) -> StarState:
    """Remove a star from a repository."""
    return await star_service.unstar(owner, repo, current_user)


@router.get("/{owner}/{repo}/stargazers")
@require_permission("repository:read", authorization="_authorization", user="_current_user", response="_response")
async def list_stargazers(
    owner: str,
    repo: str,
    star_service: StarServiceDep,
    offset: int = 0,
    limit: int = 100,
    *,
    _authorization: AuthorizationServiceDep,
    _current_user: OptionalUser,
    _response: Response,
) -> StargazersPublic:
    """List users who starred a repository."""
    return await star_service.stargazers(owner, repo, offset, limit)


@user_router.get("/me/starred")
async def list_starred_repositories(
    star_service: StarServiceDep, current_user: CurrentUser, offset: int = 0, limit: int = 100
) -> RepositoriesPublic:
    """List repositories starred by the current user."""
    return await star_service.starred_repositories(current_user.id, offset, limit, current_user)
