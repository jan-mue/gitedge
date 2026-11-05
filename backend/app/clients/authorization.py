"""Authorization facts stored in PostgreSQL, separate from the Casbin model."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, override

from sqlalchemy import String, case, cast, delete, literal, select, union_all

from app.entities.authorization import OrganizationMember, RepositoryCollaborator, Team, TeamMember
from app.entities.repositories import Repository

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy.sql.selectable import CompoundSelect

    from app.entities.organizations import Organization
    from app.permissions import ScopeGrant

type AccessEntity = OrganizationMember | Team | TeamMember | RepositoryCollaborator


def repository_role_grants(user_id: uuid.UUID) -> CompoundSelect[uuid.UUID, str]:
    """Select current direct, team, and organization-admin grants without materializing repository IDs."""
    direct = select(RepositoryCollaborator.repository_id, RepositoryCollaborator.role).where(
        RepositoryCollaborator.user_id == user_id
    )
    teams = (
        select(RepositoryCollaborator.repository_id, RepositoryCollaborator.role)
        .join(Team, Team.id == RepositoryCollaborator.team_id)
        .join(Repository, Repository.id == RepositoryCollaborator.repository_id)
        .join(TeamMember, TeamMember.team_id == Team.id)
        .join(OrganizationMember, OrganizationMember.organization_id == Team.organization_id)
        .where(
            Repository.owner_id == Team.organization_id,
            TeamMember.user_id == user_id,
            OrganizationMember.user_id == user_id,
        )
    )
    admins = (
        select(Repository.id, literal("org_admin"))
        .join(OrganizationMember, OrganizationMember.organization_id == Repository.owner_id)
        .where(
            OrganizationMember.user_id == user_id,
            OrganizationMember.is_admin.is_(True),
        )
    )
    return union_all(direct, teams, admins)


class AuthorizationStore(ABC):
    """Store contract for the facts used in authorization decisions."""

    @abstractmethod
    async def scope_grants(self, user_id: uuid.UUID, repositories: list[Repository]) -> list[ScopeGrant]:
        """Load current membership and collaborator edges for Casbin's scoped role graph."""

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

    @override
    async def scope_grants(self, user_id: uuid.UUID, repositories: list[Repository]) -> list[ScopeGrant]:
        """Read identity facts without translating organization administration into repository ownership."""
        if not repositories:
            return []
        ids = [repository.id for repository in repositories]
        subject = literal(f"user:{user_id}")
        parent = literal("/owners/") + cast(Repository.owner_id, String)
        domain = parent + "/repositories/" + cast(Repository.id, String)
        team = literal("team:") + cast(Team.id, String)
        direct = (
            select(subject, RepositoryCollaborator.role, domain)
            .select_from(RepositoryCollaborator)
            .join(Repository, Repository.id == RepositoryCollaborator.repository_id)
            .where(Repository.id.in_(ids), RepositoryCollaborator.user_id == user_id)
        )
        teams = (
            select(team, RepositoryCollaborator.role, domain)
            .select_from(Team)
            .join(RepositoryCollaborator, RepositoryCollaborator.team_id == Team.id)
            .join(Repository, Repository.id == RepositoryCollaborator.repository_id)
            .join(TeamMember, TeamMember.team_id == Team.id)
            .join(OrganizationMember, OrganizationMember.organization_id == Team.organization_id)
            .where(
                Repository.id.in_(ids),
                Repository.owner_id == Team.organization_id,
                TeamMember.user_id == user_id,
                OrganizationMember.user_id == user_id,
            )
        )
        team_memberships = teams.with_only_columns(subject, team, parent + "/*")
        organization_domain = literal("/owners/") + cast(OrganizationMember.organization_id, String)
        organization_role = case((OrganizationMember.is_admin.is_(True), "org_admin"), else_="org_member")
        members = select(subject, organization_role, organization_domain).where(
            OrganizationMember.organization_id.in_({repository.owner_id for repository in repositories}),
            OrganizationMember.user_id == user_id,
        )
        descendants = members.with_only_columns(subject, organization_role, organization_domain + "/*")
        result = await self.db.execute(union_all(direct, teams, team_memberships, members, descendants))
        return list(dict.fromkeys((subject, role, domain) for subject, role, domain in result))

    @override
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

    @override
    async def teams(self, organization_id: uuid.UUID) -> list[Team]:
        """List organization teams."""
        return list(await self.db.scalars(select(Team).where(Team.organization_id == organization_id)))

    @override
    async def team_members(self, team_id: uuid.UUID) -> list[TeamMember]:
        """List team memberships."""
        return list(await self.db.scalars(select(TeamMember).where(TeamMember.team_id == team_id)))

    @override
    async def collaborators(self, repository_id: uuid.UUID) -> list[RepositoryCollaborator]:
        """List repository role assignments."""
        return list(
            await self.db.scalars(
                select(RepositoryCollaborator).where(RepositoryCollaborator.repository_id == repository_id)
            )
        )

    @override
    async def save(self, entity: AccessEntity) -> None:
        """Persist an authorization fact."""
        self.db.add(entity)
        await self.db.commit()
        await self.db.refresh(entity)

    @override
    async def remove(self, entity: AccessEntity) -> None:
        """Delete a fact and revoke dependent team memberships."""
        if isinstance(entity, OrganizationMember):
            teams = select(Team.id).where(Team.organization_id == entity.organization_id)
            await self.db.execute(
                delete(TeamMember).where(TeamMember.team_id.in_(teams), TeamMember.user_id == entity.user_id)
            )
        await self.db.delete(entity)
        await self.db.commit()

    @override
    async def create_organization(self, organization: Organization, user_id: uuid.UUID) -> None:
        """Create an organization and its administrator in one transaction."""
        self.db.add(organization)
        await self.db.flush()
        self.db.add(OrganizationMember(organization_id=organization.id, user_id=user_id, is_admin=True))
        await self.db.commit()
        await self.db.refresh(organization)
