"""PyCasbin decisions from current database facts and a declarative policy."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.entities.authorization import Team
from app.exceptions import (
    AuthenticationError,
    ConflictError,
    InvalidInputError,
    NotFoundError,
    OrganizationNotFoundError,
    PermissionDeniedError,
    UserNotFoundError,
)
from app.permissions import Actor, Resource, owner_domain, repository_domain
from app.schemas.authorization import (
    CollaboratorPublic,
    MemberPublic,
    OrganizationMember,
    RepositoryCollaborator,
    RepositoryPermissions,
    RepositoryRole,
    TeamMember,
)

if TYPE_CHECKING:
    import uuid

    import casbin

    from app.clients.authorization import AuthorizationStore
    from app.clients.organizations import OrganizationStore
    from app.clients.repositories import RepositoryStore
    from app.clients.users import UserStore
    from app.entities.organizations import Organization
    from app.entities.repositories import Repository
    from app.entities.users import User
    from app.schemas.authorization import CollaboratorInput


class AuthorizationService:
    """Resolve scoped roles and manage validated authorization facts."""

    def __init__(
        self,
        store: AuthorizationStore,
        repositories: RepositoryStore,
        organizations: OrganizationStore,
        users: UserStore,
    ) -> None:
        """Initialize the service with data-access stores."""
        self.store = store
        self.repositories = repositories
        self.organizations = organizations
        self.users = users

    @staticmethod
    def _actor(user: User | None) -> Actor:
        """Pass identity attributes to the matcher without calculating permissions."""
        return (
            Actor(f"user:{user.id}", active=bool(user.is_active), superuser=bool(user.is_superuser))
            if user
            else Actor("anonymous")
        )

    @staticmethod
    def _resource(repository: Repository) -> Resource:
        """Pass repository attributes to the matcher."""
        return Resource(
            repository_domain(repository.owner_id, repository.id),
            f"user:{repository.owner_id}",
            not repository.is_private,
            str(repository.id),
        )

    async def _repository_enforcer(self, repositories: list[Repository], user: User | None) -> casbin.AsyncEnforcer:
        """Use the adapter-backed AsyncEnforcer directly for every authorization decision."""
        parents = {owner_domain(repository.owner_id) for repository in repositories}
        domains = [repository_domain(repository.owner_id, repository.id) for repository in repositories]
        domains.extend(parents)
        domains.extend(f"{parent}/*" for parent in parents)
        return await self.store.enforcer(user.id if user else None, domains)

    async def can(self, repository: Repository, user: User | None, permission: str = "repository:read") -> bool:
        """Ask Casbin to evaluate the account relationship and resource facts."""
        enforcer = await self._repository_enforcer([repository], user)
        return enforcer.enforce(self._actor(user), self._resource(repository), permission, "account")

    async def visible_users(
        self, repository: Repository, users: list[User], permission: str = "repository:read"
    ) -> list[User]:
        """Authorize a whole notification audience using one current relationship graph."""
        if not users:
            return []
        parent = owner_domain(repository.owner_id)
        enforcer = await self.store.audience_enforcer(
            [user.id for user in users],
            [repository_domain(repository.owner_id, repository.id), parent, f"{parent}/*"],
        )
        resource = self._resource(repository)
        return [user for user in users if enforcer.enforce(self._actor(user), resource, permission, "account")]

    async def visible_repositories(self, repositories: list[Repository], user: User | None) -> list[Repository]:
        """Use one filtered AsyncEnforcer for a bounded repository batch."""
        if not repositories:
            return []
        enforcer = await self._repository_enforcer(repositories, user)
        return [
            repository
            for repository in repositories
            if enforcer.enforce(self._actor(user), self._resource(repository), "repository:read", "account")
        ]

    async def permissions(self, repository: Repository, user: User | None) -> RepositoryPermissions:
        """Evaluate all capability flags using the same AsyncEnforcer."""
        enforcer = await self._repository_enforcer([repository], user)
        actor, resource = self._actor(user), self._resource(repository)
        return RepositoryPermissions(
            actions_read=enforcer.enforce(actor, resource, "actions:read", "account"),
            actions_write=enforcer.enforce(actor, resource, "actions:write", "account"),
            read=enforcer.enforce(actor, resource, "repository:read", "account"),
            write=enforcer.enforce(actor, resource, "git:write", "account"),
            admin=enforcer.enforce(actor, resource, "repository:write", "account"),
            owner=enforcer.enforce(actor, resource, "repository:delete", "account"),
        )

    async def require(self, repository: Repository, user: User | None, permission: str = "repository:read") -> None:
        """Require a permission before any repository content or storage access."""
        if not await self.can(repository, user, permission):
            self.deny(user)

    @staticmethod
    def deny(user: User | None) -> None:
        """Report a denied repository decision using the actor's authentication state."""
        if user is None:
            raise AuthenticationError(detail="Authentication required", challenge="Bearer")
        raise PermissionDeniedError(detail="Insufficient repository permission")

    async def organization(self, name: str, user: User, permission: str = "organization:admin") -> Organization:
        """Resolve an organization and enforce its membership policy."""
        organization = await self.organizations.get_by_name(name)
        if organization is None:
            raise OrganizationNotFoundError()
        if not await self.organization_can(organization, user, permission):
            raise PermissionDeniedError("Insufficient organization permission")
        return organization

    async def organization_can(self, organization: Organization, user: User, permission: str) -> bool:
        """Evaluate organization management with the same Casbin model."""
        domain = owner_domain(organization.id)
        enforcer = await self.store.enforcer(user.id, [domain, f"{domain}/*"])
        return enforcer.enforce(self._actor(user), Resource(domain), permission, "account")

    async def require_creation(self, owner: str, user: User) -> None:
        """Authorize creation in a personal or organization namespace through Casbin."""
        owner_id, _ = await self.repositories.resolve_owner(owner)
        domain = owner_domain(owner_id)
        enforcer = await self.store.enforcer(user.id, [domain, f"{domain}/*"])
        if not enforcer.enforce(
            self._actor(user), Resource(domain, f"user:{owner_id}"), "repository:create", "account"
        ):
            raise PermissionDeniedError("Cannot create repositories for this owner")

    async def member_public(self, member: OrganizationMember) -> MemberPublic:
        """Include public identity fields in the membership list."""
        user = await self.users.get(member.user_id)
        return MemberPublic(user_id=user.id, name=user.name, display_name=user.display_name, is_admin=member.is_admin)

    async def set_member(self, name: str, user_id: uuid.UUID, is_admin: bool, actor: User) -> OrganizationMember:
        """Add or update a member, preserving at least one organization admin."""
        organization = await self.organization(name, actor)
        if await self.users.find(user_id) is None:
            raise UserNotFoundError()
        members = await self.store.members(organization.id, for_update=True)
        member = next((member for member in members if member.user_id == user_id), None)
        if member is not None:
            self._protect_last_admin(member, members, is_admin)
            member.is_admin = is_admin
        else:
            member = OrganizationMember(organization_id=organization.id, user_id=user_id, is_admin=is_admin)
        await self.store.save(member)
        return member

    @staticmethod
    def _protect_last_admin(
        member: OrganizationMember, members: list[OrganizationMember], is_admin: bool = False
    ) -> None:
        """Prevent removing or demoting an organization's last administrator."""
        if member.is_admin and not is_admin and sum(item.is_admin for item in members) == 1:
            raise ConflictError(detail="An organization must retain an administrator")

    async def remove_member(self, name: str, user_id: uuid.UUID, actor: User) -> None:
        """Revoke organization and team membership."""
        organization = await self.organization(name, actor)
        members = await self.store.members(organization.id, for_update=True)
        member = next((member for member in members if member.user_id == user_id), None)
        if member is None:
            raise NotFoundError(detail="Member not found")
        self._protect_last_admin(member, members)
        await self.store.remove(member)

    async def create_team(self, name: str, team_name: str, actor: User) -> Team:
        """Create a uniquely named team within an organization."""
        organization = await self.organization(name, actor)
        normalized = team_name.lower()
        if any(team.name == normalized for team in await self.store.teams(organization.id)):
            raise ConflictError(detail="Team already exists")
        team = Team(organization_id=organization.id, name=normalized)
        await self.store.save(team)
        return team

    async def team(self, name: str, team_id: uuid.UUID, actor: User) -> Team:
        """Resolve a team within the organization administered by the actor."""
        organization = await self.organization(name, actor)
        team = next((team for team in await self.store.teams(organization.id) if team.id == team_id), None)
        if team is None:
            raise NotFoundError(detail="Team not found")
        return team

    async def set_team_member(self, name: str, team_id: uuid.UUID, user_id: uuid.UUID, actor: User) -> None:
        """Add an organization member to one of its teams."""
        team = await self.team(name, team_id, actor)
        if not any(member.user_id == user_id for member in await self.store.members(team.organization_id)):
            raise InvalidInputError(detail="Team members must belong to the organization")
        if not any(member.user_id == user_id for member in await self.store.team_members(team.id)):
            await self.store.save(TeamMember(team_id=team.id, user_id=user_id))

    async def set_collaborator(
        self, repository: Repository, body: CollaboratorInput, actor: User
    ) -> RepositoryCollaborator:
        """Grant a scoped role; only owners can grant or change an owner role."""
        await self.require(repository, actor, "collaborators:write")
        if body.user_id is not None and await self.users.find(body.user_id) is None:
            raise UserNotFoundError()
        if body.team_id is not None and not any(
            team.id == body.team_id for team in await self.store.teams(repository.owner_id)
        ):
            raise InvalidInputError(detail="Team must belong to the repository's organization")
        existing = next(
            (
                item
                for item in await self.store.collaborators(repository.id)
                if item.user_id == body.user_id and item.team_id == body.team_id
            ),
            None,
        )
        if body.role == RepositoryRole.OWNER or (existing is not None and existing.role == RepositoryRole.OWNER):
            await self.require(repository, actor, "collaborators:owner")
        collaborator = existing or RepositoryCollaborator(
            repository_id=repository.id, user_id=body.user_id, team_id=body.team_id
        )
        collaborator.role = body.role
        await self.store.save(collaborator)
        return collaborator

    async def remove_collaborator(self, repository: Repository, collaborator_id: uuid.UUID, actor: User) -> None:
        """Revoke a collaborator without allowing admins to revoke owners."""
        await self.require(repository, actor, "collaborators:write")
        collaborator = next(
            (item for item in await self.store.collaborators(repository.id) if item.id == collaborator_id), None
        )
        if collaborator is None:
            raise NotFoundError(detail="Collaborator not found")
        if collaborator.role == RepositoryRole.OWNER:
            await self.require(repository, actor, "collaborators:owner")
        await self.store.remove(collaborator)

    async def collaborator_public(
        self, repository: Repository, collaborator: RepositoryCollaborator
    ) -> CollaboratorPublic:
        """Resolve a collaborator's display name without exposing unrelated subjects."""
        if collaborator.user_id is not None:
            user = await self.users.get(collaborator.user_id)
            name = user.name
        else:
            teams = await self.store.teams(repository.owner_id)
            name = next(team.name for team in teams if team.id == collaborator.team_id)
        return CollaboratorPublic(
            id=collaborator.id,
            user_id=collaborator.user_id,
            team_id=collaborator.team_id,
            role=RepositoryRole(collaborator.role),
            subject_name=name,
            display_name=user.display_name if collaborator.user_id is not None else None,
        )
