"""Authorization facts stored in PostgreSQL, separate from the Casbin model."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from sqlalchemy import delete, select

from app.entities.authorization import OrganizationMember, RepositoryCollaborator, Team, TeamMember

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession

    from app.entities.organizations import Organization

type AccessEntity = OrganizationMember | Team | TeamMember | RepositoryCollaborator


class AuthorizationStore(ABC):
    """Store contract for the facts used in authorization decisions."""

    @abstractmethod
    async def members(self, organization_id: uuid.UUID, *, for_update: bool = False) -> list[OrganizationMember]:
        """List members of an organization."""

    @abstractmethod
    async def teams(self, organization_id: uuid.UUID) -> list[Team]:
        """List teams in an organization."""

    @abstractmethod
    async def team_members(self, team_id: uuid.UUID) -> list[TeamMember]:
        """List a team's members."""

    @abstractmethod
    async def collaborators(self, repository_id: uuid.UUID) -> list[RepositoryCollaborator]:
        """List a repository's explicit collaborators."""

    @abstractmethod
    async def save(self, entity: AccessEntity) -> None:
        """Insert or update an authorization fact."""

    @abstractmethod
    async def remove(self, entity: AccessEntity) -> None:
        """Remove a fact, including team memberships when leaving an organization."""

    @abstractmethod
    async def create_organization(self, organization: Organization, user_id: uuid.UUID) -> None:
        """Atomically create an organization and its first administrator."""


class SQLAuthorizationStore(AuthorizationStore):
    """SQLAlchemy implementation of the authorization fact store."""

    def __init__(self, db: AsyncSession) -> None:
        """Bind the store to the request's database session."""
        self.db = db

    async def members(self, organization_id: uuid.UUID, *, for_update: bool = False) -> list[OrganizationMember]:
        """List organization memberships."""
        statement = (
            select(OrganizationMember)
            .where(OrganizationMember.organization_id == organization_id)
            .order_by(OrganizationMember.id)
        )
        if for_update:
            statement = statement.with_for_update().execution_options(populate_existing=True)
        return list(await self.db.scalars(statement))

    async def teams(self, organization_id: uuid.UUID) -> list[Team]:
        """List organization teams."""
        return list(await self.db.scalars(select(Team).where(Team.organization_id == organization_id)))

    async def team_members(self, team_id: uuid.UUID) -> list[TeamMember]:
        """List team memberships."""
        return list(await self.db.scalars(select(TeamMember).where(TeamMember.team_id == team_id)))

    async def collaborators(self, repository_id: uuid.UUID) -> list[RepositoryCollaborator]:
        """List repository role assignments."""
        return list(
            await self.db.scalars(
                select(RepositoryCollaborator).where(RepositoryCollaborator.repository_id == repository_id)
            )
        )

    async def save(self, entity: AccessEntity) -> None:
        """Persist an authorization fact."""
        self.db.add(entity)
        await self.db.commit()
        await self.db.refresh(entity)

    async def remove(self, entity: AccessEntity) -> None:
        """Delete a fact and revoke dependent team memberships."""
        if isinstance(entity, OrganizationMember):
            teams = select(Team.id).where(Team.organization_id == entity.organization_id)
            await self.db.execute(
                delete(TeamMember).where(TeamMember.team_id.in_(teams), TeamMember.user_id == entity.user_id)
            )
        await self.db.delete(entity)
        await self.db.commit()

    async def create_organization(self, organization: Organization, user_id: uuid.UUID) -> None:
        """Create an organization and its administrator in one transaction."""
        self.db.add(organization)
        await self.db.flush()
        self.db.add(OrganizationMember(organization_id=organization.id, user_id=user_id, is_admin=True))
        await self.db.commit()
        await self.db.refresh(organization)
