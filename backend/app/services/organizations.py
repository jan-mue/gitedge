"""Service for managing organizations."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import HTTPException

from app.entities.organizations import Organization
from app.schemas.organizations import OrganizationCreate, OrganizationPublic, OrganizationsPublic

if TYPE_CHECKING:
    from app.clients.organizations import OrganizationStore
    from app.clients.users import UserStore


class OrganizationService:
    """Service for managing organizations."""

    def __init__(self, organization_store: OrganizationStore, user_store: UserStore) -> None:
        """Initialize the organization service.

        Args:
            organization_store: Organization store.
            user_store: User store used to keep the owner namespace unique.
        """
        self.organization_store = organization_store
        self.user_store = user_store

    async def create_organization(self, body: OrganizationCreate) -> OrganizationPublic:
        """Create a new organization.

        Args:
            body: Organization creation data.

        Returns:
            The created organization.

        Raises:
            HTTPException: If the name is already taken by a user or organization.
        """
        name = body.name.strip()
        if await self.user_store.get_by_name(name) is not None:
            raise HTTPException(status_code=409, detail="An owner with that name already exists")
        if await self.organization_store.get_by_name(name) is not None:
            raise HTTPException(status_code=409, detail="An owner with that name already exists")

        organization = Organization(
            name=name,
            lower_name=name.lower(),
            display_name=body.display_name,
            description=body.description,
        )
        await self.organization_store.add(organization)
        return OrganizationPublic.model_validate(organization)

    async def list_organizations(self, offset: int = 0, limit: int = 100) -> OrganizationsPublic:
        """List organizations.

        Args:
            offset: Pagination offset.
            limit: Maximum number of organizations.

        Returns:
            OrganizationsPublic with the organizations.
        """
        organizations = await self.organization_store.get_all(offset=offset, limit=limit)
        count = await self.organization_store.count()
        return OrganizationsPublic(
            data=[OrganizationPublic.model_validate(organization) for organization in organizations],
            count=count,
        )
