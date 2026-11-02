"""Organization store for database operations."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, override

from sqlalchemy import select

from app.clients.database import CrudStore, SQLStore
from app.entities.organizations import Organization
from app.exceptions import OrganizationNotFoundError

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class OrganizationStore(CrudStore[Organization], ABC):
    """Abstract organization store with additional organization-specific methods."""

    @abstractmethod
    async def find_by_name(self, name: str) -> Organization | None:
        """Find an organization by its name (case-insensitive), returning None when absent."""

    async def get_by_name(self, name: str) -> Organization:
        """Get an organization by its name (case-insensitive), raising when absent.

        Raises:
            OrganizationNotFoundError: If no organization matches the name.
        """
        organization = await self.find_by_name(name)
        if organization is None:
            raise OrganizationNotFoundError
        return organization


class SQLOrganizationStore(OrganizationStore, SQLStore[Organization]):
    """SQLAlchemy implementation of organization store."""

    def __init__(self, db: AsyncSession) -> None:
        """Initialize the organization store.

        Args:
            db: SQLAlchemy async session.
        """
        super().__init__(db, Organization)

    @override
    async def find_by_name(self, name: str) -> Organization | None:
        """Find an organization by its name (case-insensitive), returning None when absent."""
        return await self.db.scalar(select(Organization).where(Organization.lower_name == name.lower()))
