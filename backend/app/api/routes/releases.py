"""Repository release and tag routes."""

from __future__ import annotations

from fastapi import APIRouter, Response

from app.api.dependencies import (
    AuthorizationServiceDep,
    CurrentUser,
    OptionalUser,
    ReleaseServiceDep,
    RepositoryServiceDep,
)
from app.api.permissions import require_permission
from app.schemas.releases import ReleaseCreate, ReleasePublic, ReleasesPublic, ReleaseUpdate, TagsPublic

router = APIRouter(prefix="/repositories", tags=["releases"])


@router.get("/{owner}/{repo}/releases")
@require_permission("repository:read", authorization="_authorization", response="_response")
async def list_releases(
    owner: str,
    repo: str,
    release_service: ReleaseServiceDep,
    current_user: OptionalUser,
    include_drafts: bool = False,
    *,
    _authorization: AuthorizationServiceDep,
    _response: Response,
) -> ReleasesPublic:
    """List releases for a repository."""
    return await release_service.list_releases(owner, repo, include_drafts, current_user)


@router.post("/{owner}/{repo}/releases", status_code=201)
@require_permission("repository:write", authorization="_authorization", response="_response")
async def create_release(
    owner: str,
    repo: str,
    body: ReleaseCreate,
    release_service: ReleaseServiceDep,
    current_user: CurrentUser,
    *,
    _authorization: AuthorizationServiceDep,
    _response: Response,
) -> ReleasePublic:
    """Create a release."""
    return await release_service.create_release(owner, repo, body, current_user)


@router.get("/{owner}/{repo}/releases/{tag_name}")
@require_permission("repository:read", authorization="_authorization", response="_response")
async def get_release(
    owner: str,
    repo: str,
    tag_name: str,
    release_service: ReleaseServiceDep,
    current_user: OptionalUser,
    *,
    _authorization: AuthorizationServiceDep,
    _response: Response,
) -> ReleasePublic:
    """Get a single release by tag name."""
    return await release_service.get_release(owner, repo, tag_name, current_user)


@router.patch("/{owner}/{repo}/releases/{tag_name}")
@require_permission("repository:write", authorization="_authorization", response="_response")
async def update_release(
    owner: str,
    repo: str,
    tag_name: str,
    body: ReleaseUpdate,
    release_service: ReleaseServiceDep,
    current_user: CurrentUser,
    *,
    _authorization: AuthorizationServiceDep,
    _response: Response,
) -> ReleasePublic:
    """Update a release."""
    return await release_service.update_release(owner, repo, tag_name, body, current_user)


@router.get("/{owner}/{repo}/tags")
@require_permission("repository:read", authorization="_authorization", user="_current_user", response="_response")
async def list_tags(
    owner: str,
    repo: str,
    repository_service: RepositoryServiceDep,
    *,
    _authorization: AuthorizationServiceDep,
    _current_user: OptionalUser,
    _response: Response,
) -> TagsPublic:
    """List Git tags for a repository."""
    return await repository_service.list_tags(owner, repo)
