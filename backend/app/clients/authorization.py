"""Authorization facts stored in PostgreSQL, separate from the Casbin model."""

from __future__ import annotations

from abc import ABC, abstractmethod
from copy import deepcopy
from typing import TYPE_CHECKING, override

import casbin
from sqlalchemy import String, and_, cast, delete, literal, select, union_all
from sqlalchemy.orm import aliased

from app.clients.casbin import RelationshipAdapter, RelationshipFilter
from app.entities.authorization import OrganizationMember, RepositoryCollaborator, Team, TeamMember
from app.entities.casbin import CasbinRule
from app.entities.repositories import Repository
from app.exceptions import NotFoundError
from app.permissions import owner_domain, repository_domain, scoped_policy_model

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy.sql.selectable import CompoundSelect

    from app.entities.organizations import Organization
    from app.permissions import ScopeGrant

type AccessEntity = OrganizationMember | Team | TeamMember | RepositoryCollaborator


def repository_role_grants(user_id: uuid.UUID) -> CompoundSelect[uuid.UUID, str]:
    """Project persisted Casbin relationships into SQL visibility without materializing IDs."""
    subject = f"user:{user_id}"
    parent = literal("/owners/") + cast(Repository.owner_id, String)
    domain = parent + "/repositories/" + cast(Repository.id, String)
    direct = select(Repository.id.label("repository_id"), CasbinRule.v1.label("role")).join(
        CasbinRule, and_(CasbinRule.ptype == "g2", CasbinRule.v0 == subject, CasbinRule.v2 == domain)
    )
    grant, team_member, organization_member = (aliased(CasbinRule) for _ in range(3))
    teams = (
        select(Repository.id, grant.v1.label("role"))
        .join(grant, and_(grant.ptype == "g2", grant.v0.startswith("team:"), grant.v2 == domain))
        .join(
            team_member,
            and_(
                team_member.ptype == "g2",
                team_member.v0 == subject,
                team_member.v1 == grant.v0,
                team_member.v2 == parent + "/*",
            ),
        )
        .join(
            organization_member,
            and_(
                organization_member.ptype == "g2",
                organization_member.v0 == subject,
                organization_member.v1.in_(["org_admin", "org_member"]),
                organization_member.v2 == team_member.v2,
            ),
        )
    )
    organizations = select(Repository.id, CasbinRule.v1.label("role")).join(
        CasbinRule,
        and_(
            CasbinRule.ptype == "g2",
            CasbinRule.v0 == subject,
            CasbinRule.v2 == parent + "/*",
            CasbinRule.v1.in_(["org_admin", "org_member"]),
        ),
    )
    return union_all(direct, teams, organizations)


class AuthorizationStore(ABC):
    """Store contract for the facts used in authorization decisions."""

    @abstractmethod
    async def scope_grants(self, user_id: uuid.UUID, repositories: list[Repository]) -> list[ScopeGrant]:
        """Load current membership and collaborator edges for Casbin's scoped role graph."""

    @abstractmethod
    async def organization_grants(self, user_id: uuid.UUID, organization_id: uuid.UUID) -> list[ScopeGrant]:
        """Load the actor's persisted relationships in an organization's domain."""

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
        parents = {owner_domain(repository.owner_id) for repository in repositories}
        domains = [repository_domain(repository.owner_id, repository.id) for repository in repositories]
        domains.extend(parents)
        domains.extend(f"{parent}/*" for parent in parents)
        return await self._load_grants(user_id, domains)

    @override
    async def organization_grants(self, user_id: uuid.UUID, organization_id: uuid.UUID) -> list[ScopeGrant]:
        """Use persisted Casbin relationships for organization administration as well."""
        domain = owner_domain(organization_id)
        return await self._load_grants(user_id, [domain, f"{domain}/*"])

    async def _load_grants(self, user_id: uuid.UUID, domains: list[str]) -> list[ScopeGrant]:
        """Reload only this actor's relevant policy subset, using the external request session."""
        adapter = RelationshipAdapter(self.db)
        enforcer = casbin.AsyncEnforcer(deepcopy(scoped_policy_model()), adapter)
        enforcer.enable_auto_save(False)
        await enforcer.load_filtered_policy(RelationshipFilter(f"user:{user_id}", domains))
        return [(subject, relation, domain) for subject, relation, domain in enforcer.get_named_grouping_policy("g2")]

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
        await self.db.flush()
        await self._save_relationships(entity)
        await self.db.commit()
        await self.db.refresh(entity)

    async def _save_relationships(self, entity: AccessEntity) -> None:
        """Persist identity metadata and Casbin relationships atomically through the adapter."""
        adapter = RelationshipAdapter(self.db)
        if isinstance(entity, OrganizationMember):
            subject = f"user:{entity.user_id}"
            domain = owner_domain(entity.organization_id)
            for role in ("org_admin", "org_member"):
                for scope in (domain, f"{domain}/*"):
                    await adapter.remove_filtered_policy("g", "g2", 0, subject, role, scope)
            role = "org_admin" if entity.is_admin else "org_member"
            await adapter.add_policies("g", "g2", [[subject, role, domain], [subject, role, f"{domain}/*"]])
        elif isinstance(entity, TeamMember):
            team = await self.db.get(Team, entity.team_id)
            if team is None:
                raise NotFoundError(detail="Team not found")
            member = await self.db.scalar(
                select(OrganizationMember).where(
                    OrganizationMember.organization_id == team.organization_id,
                    OrganizationMember.user_id == entity.user_id,
                )
            )
            if member is not None:
                rule = [f"user:{entity.user_id}", f"team:{team.id}", f"{owner_domain(team.organization_id)}/*"]
                await adapter.remove_policy("g", "g2", rule)
                await adapter.add_policy("g", "g2", rule)
        elif isinstance(entity, RepositoryCollaborator):
            repository = await self.db.get(Repository, entity.repository_id)
            if repository is None:
                raise NotFoundError(detail="Repository not found")
            subject = f"user:{entity.user_id}" if entity.user_id is not None else f"team:{entity.team_id}"
            domain = repository_domain(repository.owner_id, repository.id)
            await adapter.remove_filtered_policy("g", "g2", 0, subject, "", domain)
            await adapter.add_policy("g", "g2", [subject, entity.role, domain])

    @override
    async def remove(self, entity: AccessEntity) -> None:
        """Revoke persisted relationships in the same transaction as identity metadata."""
        adapter = RelationshipAdapter(self.db)
        if isinstance(entity, OrganizationMember):
            teams = select(Team.id).where(Team.organization_id == entity.organization_id)
            await self.db.execute(
                delete(TeamMember).where(TeamMember.team_id.in_(teams), TeamMember.user_id == entity.user_id)
            )
            subject = f"user:{entity.user_id}"
            domain = owner_domain(entity.organization_id)
            await adapter.remove_filtered_policy("g", "g2", 0, subject, "", domain)
            await adapter.remove_filtered_policy("g", "g2", 0, subject, "", f"{domain}/*")
        elif isinstance(entity, Team):
            await adapter.remove_filtered_policy("g", "g2", 0, f"team:{entity.id}")
            await adapter.remove_filtered_policy("g", "g2", 1, f"team:{entity.id}")
        elif isinstance(entity, TeamMember):
            await adapter.remove_filtered_policy("g", "g2", 0, f"user:{entity.user_id}", f"team:{entity.team_id}")
        elif isinstance(entity, RepositoryCollaborator):
            repository = await self.db.get(Repository, entity.repository_id)
            if repository is None:
                raise NotFoundError(detail="Repository not found")
            subject = f"user:{entity.user_id}" if entity.user_id is not None else f"team:{entity.team_id}"
            await adapter.remove_filtered_policy(
                "g", "g2", 0, subject, "", repository_domain(repository.owner_id, repository.id)
            )
        await self.db.delete(entity)
        await self.db.commit()

    @override
    async def create_organization(self, organization: Organization, user_id: uuid.UUID) -> None:
        """Create an organization and its administrator in one transaction."""
        self.db.add(organization)
        await self.db.flush()
        member = OrganizationMember(organization_id=organization.id, user_id=user_id, is_admin=True)
        self.db.add(member)
        await self.db.flush()
        await self._save_relationships(member)
        await self.db.commit()
        await self.db.refresh(organization)
