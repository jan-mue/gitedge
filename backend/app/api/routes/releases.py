"""Repository release and tag routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.dependencies import CurrentUser, OptionalUser, ReleaseServiceDep, RepositoryServiceDep, require_repository
from app.schemas.releases import ReleaseCreate, ReleasePublic, ReleasesPublic, ReleaseUpdate, TagsPublic

router = APIRouter(prefix="/repositories", tags=["releases"])


@router.get("/{owner}/{repo}/releases", dependencies=[Depends(require_repository("repository:read"))])
async def list_releases(
    owner: str, repo: str, release_service: ReleaseServiceDep, user: OptionalUser, include_drafts: bool = False
) -> ReleasesPublic:
    """List releases for a repository."""
    return await release_service.list_releases(owner, repo, include_drafts, user)


@router.post(
    "/{owner}/{repo}/releases", status_code=201, dependencies=[Depends(require_repository("repository:write"))]
)
async def create_release(
    owner: str, repo: str, body: ReleaseCreate, release_service: ReleaseServiceDep, current_user: CurrentUser
) -> ReleasePublic:
    """Create a release."""
    return await release_service.create_release(owner, repo, body, current_user)


@router.get("/{owner}/{repo}/releases/{tag_name}", dependencies=[Depends(require_repository("repository:read"))])
async def get_release(
    owner: str, repo: str, tag_name: str, release_service: ReleaseServiceDep, user: OptionalUser
) -> ReleasePublic:
    """Get a single release by tag name."""
    return await release_service.get_release(owner, repo, tag_name, user)


@router.patch("/{owner}/{repo}/releases/{tag_name}", dependencies=[Depends(require_repository("repository:write"))])
async def update_release(
    owner: str,
    repo: str,
    tag_name: str,
    body: ReleaseUpdate,
    release_service: ReleaseServiceDep,
    current_user: CurrentUser,
) -> ReleasePublic:
    """Update a release."""
    return await release_service.update_release(owner, repo, tag_name, body, current_user)


@router.get("/{owner}/{repo}/tags", dependencies=[Depends(require_repository("repository:read"))])
async def list_tags(owner: str, repo: str, repository_service: RepositoryServiceDep) -> TagsPublic:
    """List Git tags for a repository."""
    return await repository_service.list_tags(owner, repo)
