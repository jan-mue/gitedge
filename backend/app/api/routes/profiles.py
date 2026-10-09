"""Principal profile routes."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, HTTPException

from app.api.dependencies import OrganizationStoreDep, RepositoryServiceDep, StarServiceDep, UserStoreDep
from app.schemas.repositories import RepositoriesPublic
from app.schemas.users import ProfilePublic

if TYPE_CHECKING:
    from app.entities.principals import Principal

router = APIRouter(prefix="/users", tags=["profiles"])


async def _resolve_principal(
    username: str, user_store: UserStoreDep, organization_store: OrganizationStoreDep
) -> Principal:
    """Resolve a name to a principal (user or organization).

    Args:
        username: The principal name.
        user_store: User store.
        organization_store: Organization store.

    Returns:
        The matching principal.

    Raises:
        HTTPException: If no user or organization matches the name.
    """
    principal: Principal | None = await user_store.get_by_name(username)
    if principal is None:
        principal = await organization_store.get_by_name(username)
    if principal is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    return principal


@router.get("/{username}")
async def read_user_by_username(
    username: str, user_store: UserStoreDep, organization_store: OrganizationStoreDep
) -> ProfilePublic:
    """Get a profile (user or organization) by name."""
    principal = await _resolve_principal(username, user_store, organization_store)
    return ProfilePublic.model_validate(principal)


@router.get("/{username}/repositories")
async def list_user_repositories(
    username: str,
    user_store: UserStoreDep,
    organization_store: OrganizationStoreDep,
    repository_service: RepositoryServiceDep,
) -> RepositoriesPublic:
    """List repositories owned by a user or organization."""
    principal = await _resolve_principal(username, user_store, organization_store)
    return await repository_service.get_user_repositories(principal.id)


@router.get("/{username}/starred")
async def list_user_starred_repositories(
    username: str,
    user_store: UserStoreDep,
    star_service: StarServiceDep,
) -> RepositoriesPublic:
    """List repositories starred by a user.

    Raises:
        HTTPException: If no user matches the name (organizations cannot star).
    """
    user = await user_store.get_by_name(username)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return await star_service.starred_repositories(user.id)
