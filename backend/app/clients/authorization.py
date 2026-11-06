"""Authorization facts stored in PostgreSQL, separate from the Casbin model."""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, override

from sqlalchemy import String, and_, cast, false, literal, or_, select, true, union_all
from sqlalchemy.orm import aliased

from app.clients.casbin import RelationshipAdapter, RelationshipFilter
from app.entities.authorization import Team
from app.entities.casbin import CasbinRule
from app.entities.organizations import Organization
from app.entities.repositories import Repository
from app.exceptions import NotFoundError
from app.permissions import owner_domain, policy_enforcer, repository_domain
from app.schemas.authorization import OrganizationMember, RepositoryCollaborator, TeamMember

if TYPE_CHECKING:
    import casbin
    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy.sql.elements import ColumnElement
    from sqlalchemy.sql.selectable import CompoundSelect

    from app.permissions import RepositoryVisibility


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


def repository_visibility_predicate(visibility: RepositoryVisibility) -> ColumnElement[bool]:
    """Apply Casbin's compiled decisions to persisted Casbin relationships in SQL."""
    if visibility.unrestricted:
        return true()
    predicates: list[ColumnElement[bool]] = [false()]
    if visibility.public_read:
        predicates.append(Repository.is_private.is_(False))
    if visibility.user_id is not None:
        if visibility.owned_read:
            predicates.append(Repository.owner_id == visibility.user_id)
        grants = repository_role_grants(visibility.user_id).subquery()
        predicates.append(Repository.id.in_(select(grants.c.repository_id).where(grants.c.role.in_(visibility.roles))))
    return or_(*predicates)


class AuthorizationStore(ABC):
    """Casbin policy management and team identity persistence."""

    @abstractmethod
    async def enforcer(self, user_id: uuid.UUID | None, domains: list[str]) -> casbin.AsyncEnforcer:
        """Load one current, filtered AsyncEnforcer for authorization."""

    @abstractmethod
    async def members(self, organization_id: uuid.UUID, *, for_update: bool = False) -> list[OrganizationMember]:
        """Project organization members from Casbin policies."""

    @abstractmethod
    async def teams(self, organization_id: uuid.UUID) -> list[Team]:
        """List organization team identities."""

    @abstractmethod
    async def team_members(self, team_id: uuid.UUID) -> list[TeamMember]:
        """Project team members from Casbin policies."""

    @abstractmethod
    async def collaborators(self, repository_id: uuid.UUID) -> list[RepositoryCollaborator]:
        """Project collaborator grants from Casbin policies."""

    @abstractmethod
    async def save(self, entity: AccessEntity) -> None:
        """Write a team identity or a Casbin relationship."""

    @abstractmethod
    async def remove(self, entity: AccessEntity) -> None:
        """Delete an identity or revoke its Casbin relationships."""

    @abstractmethod
    async def create_organization(self, organization: Organization, user_id: uuid.UUID) -> None:
        """Create an organization and its initial Casbin administrator atomically."""


def relationship_id(subject: str, domain: str) -> uuid.UUID:
    """Identify a management projection without maintaining a parallel permission record."""
    return uuid.uuid5(uuid.NAMESPACE_URL, f"gitedge:{subject}:{domain}")


class SQLAuthorizationStore(AuthorizationStore):
    """The official adapter owns all membership and collaborator persistence."""

    def __init__(self, db: AsyncSession) -> None:
        """Use the request's database transaction."""
        self.db = db

    @override
    async def enforcer(self, user_id: uuid.UUID | None, domains: list[str]) -> casbin.AsyncEnforcer:
        """Load current relationships without copying them into a synchronous enforcer."""
        if user_id is None:
            return await policy_enforcer()
        return await policy_enforcer(RelationshipAdapter(self.db), RelationshipFilter(f"user:{user_id}", domains))

    async def _policies(self, domains: list[str]) -> casbin.AsyncEnforcer:
        """Load the management scope for Casbin's policy APIs."""
        return await policy_enforcer(RelationshipAdapter(self.db), RelationshipFilter(None, domains))

    @override
    async def members(self, organization_id: uuid.UUID, *, for_update: bool = False) -> list[OrganizationMember]:
        """Read membership from Casbin, locking the organization to protect its last administrator."""
        if for_update:
            await self.db.execute(select(Organization).where(Organization.id == organization_id).with_for_update())
        domain = owner_domain(organization_id)
        enforcer = await self._policies([domain])
        return [
            OrganizationMember(
                id=relationship_id(subject, scope),
                organization_id=organization_id,
                user_id=uuid.UUID(subject.removeprefix("user:")),
                is_admin=role == "org_admin",
            )
            for subject, role, scope in enforcer.get_named_grouping_policy("g2")
            if scope == domain and role in ("org_admin", "org_member") and subject.startswith("user:")
        ]

    @override
    async def teams(self, organization_id: uuid.UUID) -> list[Team]:
        """Teams contain only names and organization identity, never permissions."""
        return list(await self.db.scalars(select(Team).where(Team.organization_id == organization_id)))

    @override
    async def team_members(self, team_id: uuid.UUID) -> list[TeamMember]:
        """Read team membership grouping policies."""
        team = await self.db.get(Team, team_id)
        if team is None:
            return []
        domain = f"{owner_domain(team.organization_id)}/*"
        enforcer = await self._policies([domain])
        return [
            TeamMember(
                id=relationship_id(subject, f"{scope}:{relation}"),
                team_id=team_id,
                user_id=uuid.UUID(subject.removeprefix("user:")),
            )
            for subject, relation, scope in enforcer.get_named_grouping_policy("g2")
            if scope == domain and relation == f"team:{team_id}" and subject.startswith("user:")
        ]

    @override
    async def collaborators(self, repository_id: uuid.UUID) -> list[RepositoryCollaborator]:
        """Read repository role bindings exclusively from Casbin."""
        repository = await self.db.get(Repository, repository_id)
        if repository is None:
            return []
        domain = repository_domain(repository.owner_id, repository.id)
        enforcer = await self._policies([domain])
        return [
            RepositoryCollaborator(
                id=relationship_id(subject, scope),
                repository_id=repository_id,
                user_id=uuid.UUID(subject[5:]) if subject.startswith("user:") else None,
                team_id=uuid.UUID(subject[5:]) if subject.startswith("team:") else None,
                role=role,
            )
            for subject, role, scope in enforcer.get_named_grouping_policy("g2")
            if scope == domain and subject.startswith(("user:", "team:"))
        ]

    @override
    async def save(self, entity: AccessEntity) -> None:
        """Mutate policies through AsyncEnforcer; there are no duplicate grant tables."""
        if isinstance(entity, Team):
            self.db.add(entity)
            await self.db.commit()
            await self.db.refresh(entity)
            return
        if isinstance(entity, OrganizationMember):
            subject = f"user:{entity.user_id}"
            domain = owner_domain(entity.organization_id)
            enforcer = await self._policies([domain, f"{domain}/*"])
            for role in ("org_admin", "org_member"):
                for scope in (domain, f"{domain}/*"):
                    await enforcer.remove_filtered_named_grouping_policy("g2", 0, subject, role, scope)
            role = "org_admin" if entity.is_admin else "org_member"
            await enforcer.add_named_grouping_policies("g2", [[subject, role, domain], [subject, role, f"{domain}/*"]])
        elif isinstance(entity, TeamMember):
            team = await self.db.get(Team, entity.team_id)
            if team is None:
                raise NotFoundError("Team not found")
            subject = f"user:{entity.user_id}"
            domain = f"{owner_domain(team.organization_id)}/*"
            enforcer = await self._policies([domain])
            await enforcer.add_named_grouping_policy("g2", subject, f"team:{entity.team_id}", domain)
        else:
            repository = await self.db.get(Repository, entity.repository_id)
            if repository is None:
                raise NotFoundError("Repository not found")
            subject = f"user:{entity.user_id}" if entity.user_id is not None else f"team:{entity.team_id}"
            domain = repository_domain(repository.owner_id, repository.id)
            enforcer = await self._policies([domain])
            await enforcer.remove_filtered_named_grouping_policy("g2", 0, subject, "", domain)
            await enforcer.add_named_grouping_policy("g2", subject, entity.role, domain)
        entity.id = relationship_id(
            subject, f"{domain}:team:{entity.team_id}" if isinstance(entity, TeamMember) else domain
        )
        await self.db.commit()

    @override
    async def remove(self, entity: AccessEntity) -> None:
        """Revoke the selected grouping policies with AsyncEnforcer."""
        if isinstance(entity, Team):
            enforcer = await policy_enforcer(
                RelationshipAdapter(self.db), RelationshipFilter(f"team:{entity.id}", None)
            )
            await enforcer.remove_filtered_named_grouping_policy("g2", 0, f"team:{entity.id}")
            await enforcer.remove_filtered_named_grouping_policy("g2", 1, f"team:{entity.id}")
            await self.db.delete(entity)
        elif isinstance(entity, OrganizationMember):
            domain = owner_domain(entity.organization_id)
            enforcer = await self._policies([domain, f"{domain}/*"])
            for scope in (domain, f"{domain}/*"):
                await enforcer.remove_filtered_named_grouping_policy("g2", 0, f"user:{entity.user_id}", "", scope)
        elif isinstance(entity, TeamMember):
            team = await self.db.get(Team, entity.team_id)
            if team is None:
                return
            enforcer = await self._policies([f"{owner_domain(team.organization_id)}/*"])
            await enforcer.remove_filtered_named_grouping_policy(
                "g2", 0, f"user:{entity.user_id}", f"team:{entity.team_id}"
            )
        else:
            repository = await self.db.get(Repository, entity.repository_id)
            if repository is None:
                return
            domain = repository_domain(repository.owner_id, repository.id)
            enforcer = await self._policies([domain])
            subject = f"user:{entity.user_id}" if entity.user_id else f"team:{entity.team_id}"
            await enforcer.remove_filtered_named_grouping_policy("g2", 0, subject, "", domain)
        await self.db.commit()

    @override
    async def create_organization(self, organization: Organization, user_id: uuid.UUID) -> None:
        """Create the organization identity and Casbin administrator in one transaction."""
        self.db.add(organization)
        await self.db.flush()
        await self.save(OrganizationMember(organization_id=organization.id, user_id=user_id, is_admin=True))
        await self.db.refresh(organization)
