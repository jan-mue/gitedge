"""Repository star routes."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.dependencies import CurrentUser, StarServiceDep
from app.schemas.repositories import RepositoriesPublic
from app.schemas.social import StargazersPublic, StarState

router = APIRouter(prefix="/repositories", tags=["stars"])
user_router = APIRouter(prefix="/users", tags=["stars"])


@router.get("/{owner}/{repo}/star")
async def get_star_state(owner: str, repo: str, star_service: StarServiceDep, current_user: CurrentUser) -> StarState:
    """Get the current user's star state for a repository."""
    return await star_service.state(owner, repo, current_user)


@router.put("/{owner}/{repo}/star")
async def star_repository(owner: str, repo: str, star_service: StarServiceDep, current_user: CurrentUser) -> StarState:
    """Star a repository."""
    return await star_service.star(owner, repo, current_user)


@router.delete("/{owner}/{repo}/star")
async def unstar_repository(
    owner: str, repo: str, star_service: StarServiceDep, current_user: CurrentUser
) -> StarState:
    """Remove a star from a repository."""
    return await star_service.unstar(owner, repo, current_user)


@router.get("/{owner}/{repo}/stargazers")
async def list_stargazers(
    owner: str, repo: str, star_service: StarServiceDep, offset: int = 0, limit: int = 100
) -> StargazersPublic:
    """List users who starred a repository."""
    return await star_service.stargazers(owner, repo, offset, limit)


@user_router.get("/me/starred")
async def list_starred_repositories(
    star_service: StarServiceDep, current_user: CurrentUser, offset: int = 0, limit: int = 100
) -> RepositoriesPublic:
    """List repositories starred by the current user."""
    return await star_service.starred_repositories(current_user.id, offset, limit)
