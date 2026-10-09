"""Organization routes."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.dependencies import CurrentUser, OrganizationServiceDep
from app.schemas.organizations import OrganizationCreate, OrganizationPublic, OrganizationsPublic

router = APIRouter(prefix="/organizations", tags=["organizations"])


@router.get("/")
async def list_organizations(
    organization_service: OrganizationServiceDep, offset: int = 0, limit: int = 100
) -> OrganizationsPublic:
    """List organizations."""
    return await organization_service.list_organizations(offset, limit)


@router.post("/", status_code=201)
async def create_organization(
    body: OrganizationCreate, organization_service: OrganizationServiceDep, _current_user: CurrentUser
) -> OrganizationPublic:
    """Create a new organization."""
    return await organization_service.create_organization(body)
