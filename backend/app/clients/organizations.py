"""Organization store for database operations."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from sqlalchemy import select

from app.clients.database import CrudStore, SQLStore
from app.entities.organizations import Organization

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class OrganizationStore(CrudStore[Organization], ABC):
    """Abstract organization store with additional organization-specific methods."""

    @abstractmethod
    async def get_by_name(self, name: str) -> Organization | None:
        """Get an organization by its name (case-insensitive)."""


class SQLOrganizationStore(OrganizationStore, SQLStore[Organization]):
    """SQLAlchemy implementation of organization store."""

    def __init__(self, db: AsyncSession) -> None:
        """Initialize the organization store.

        Args:
            db: SQLAlchemy async session.
        """
        super().__init__(db, Organization)

    async def get_by_name(self, name: str) -> Organization | None:
        """Get an organization by its name (case-insensitive)."""
        return await self.db.scalar(select(Organization).where(Organization.lower_name == name.lower()))
