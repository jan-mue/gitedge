"""PyCasbin decisions from current database facts and a declarative policy."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import casbin
from casbin.persist.adapters.asyncio import AsyncFileAdapter
from fastapi import HTTPException

from app.entities.authorization import OrganizationMember, RepositoryCollaborator, Team, TeamMember
from app.entities.principals import PrincipalType
from app.schemas.authorization import CollaboratorPublic, RepositoryRole

if TYPE_CHECKING:
    import uuid

    from app.clients.authorization import AuthorizationStore
    from app.clients.organizations import OrganizationStore
    from app.clients.repositories import RepositoryStore
    from app.clients.users import UserStore
    from app.entities.organizations import Organization
    from app.entities.repositories import Repository
    from app.entities.users import User
    from app.schemas.authorization import CollaboratorInput

POLICY_DIRECTORY = Path(__file__).resolve().parents[2] / "resources" / "authorization"


async def new_enforcer() -> casbin.AsyncEnforcer:
    """Create an isolated enforcer; never share mutable request policies."""
    enforcer = casbin.AsyncEnforcer(
        str(POLICY_DIRECTORY / "model.conf"), AsyncFileAdapter(str(POLICY_DIRECTORY / "policy.csv"))
    )
    enforcer.enable_auto_save(False)
    await enforcer.load_policy()
    return enforcer


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

    async def can(self, repository: Repository, user: User | None, permission: str = "repository:read") -> bool:
        """Evaluate a permission in a repository's UUID domain."""
        enforcer = await new_enforcer()
        domain = f"repository:{repository.id}"
        subject = f"user:{user.id}" if user else "anonymous"
        if not repository.is_private:
            await enforcer.add_grouping_policy(subject, "read", domain)
        if user is not None:
            if not user.is_active:
                return False
            if user.is_superuser or repository.owner_id == user.id:
                await enforcer.add_grouping_policy(subject, "owner", domain)
            members = await self.store.members(repository.owner_id)
            member = next((member for member in members if member.user_id == user.id), None)
            if member is not None and member.is_admin:
                await enforcer.add_grouping_policy(subject, "owner", domain)
            for collaborator in await self.store.collaborators(repository.id):
                if collaborator.user_id == user.id:
                    await enforcer.add_grouping_policy(subject, collaborator.role, domain)
                elif collaborator.team_id is not None and member is not None:
                    # Organization membership is required even if a stale team row exists.
                    teams = await self.store.teams(repository.owner_id)
                    if any(team.id == collaborator.team_id for team in teams):
                        team_members = await self.store.team_members(collaborator.team_id)
                        if any(team_member.user_id == user.id for team_member in team_members):
                            team_subject = f"team:{collaborator.team_id}"
                            await enforcer.add_grouping_policy(subject, team_subject, domain)
                            await enforcer.add_grouping_policy(team_subject, collaborator.role, domain)
        return bool(enforcer.enforce(subject, domain, permission))

    async def require(self, repository: Repository, user: User | None, permission: str = "repository:read") -> None:
        """Require a permission before any repository content or storage access."""
        if not await self.can(repository, user, permission):
            if user is None:
                raise HTTPException(
                    status_code=401, detail="Authentication required", headers={"WWW-Authenticate": "Bearer"}
                )
            raise HTTPException(status_code=403, detail="Insufficient repository permission")

    async def organization(self, name: str, user: User, permission: str = "organization:admin") -> Organization:
        """Resolve an organization and enforce its membership policy."""
        organization = await self.organizations.get_by_name(name)
        if organization is None:
            raise HTTPException(status_code=404, detail="Organization not found")
        enforcer = await new_enforcer()
        domain = f"organization:{organization.id}"
        subject = f"user:{user.id}"
        if user.is_superuser:
            await enforcer.add_grouping_policy(subject, "org_admin", domain)
        for member in await self.store.members(organization.id):
            if member.user_id == user.id:
                await enforcer.add_grouping_policy(subject, "org_admin" if member.is_admin else "org_member", domain)
        if not user.is_active or not enforcer.enforce(subject, domain, permission):
            raise HTTPException(status_code=403, detail="Insufficient organization permission")
        return organization

    async def require_creation(self, owner: str, user: User) -> None:
        """Require ownership of a personal namespace or administration of an org."""
        owner_id, owner_type = await self.repositories.resolve_owner(owner)
        if owner_type == PrincipalType.ORGANIZATION:
            await self.organization(owner, user)
        elif owner_id != user.id and not user.is_superuser:
            raise HTTPException(status_code=403, detail="Cannot create repositories for another user")

    async def set_member(self, name: str, user_id: uuid.UUID, is_admin: bool, actor: User) -> OrganizationMember:
        """Add or update a member, preserving at least one organization admin."""
        organization = await self.organization(name, actor)
        if await self.users.find(user_id) is None:
            raise HTTPException(status_code=404, detail="User not found")
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
            raise HTTPException(status_code=409, detail="An organization must retain an administrator")

    async def remove_member(self, name: str, user_id: uuid.UUID, actor: User) -> None:
        """Revoke organization and team membership."""
        organization = await self.organization(name, actor)
        members = await self.store.members(organization.id, for_update=True)
        member = next((member for member in members if member.user_id == user_id), None)
        if member is None:
            raise HTTPException(status_code=404, detail="Member not found")
        self._protect_last_admin(member, members)
        await self.store.remove(member)

    async def create_team(self, name: str, team_name: str, actor: User) -> Team:
        """Create a uniquely named team within an organization."""
        organization = await self.organization(name, actor)
        normalized = team_name.lower()
        if any(team.name == normalized for team in await self.store.teams(organization.id)):
            raise HTTPException(status_code=409, detail="Team already exists")
        team = Team(organization_id=organization.id, name=normalized)
        await self.store.save(team)
        return team

    async def team(self, name: str, team_id: uuid.UUID, actor: User) -> Team:
        """Resolve a team within the organization administered by the actor."""
        organization = await self.organization(name, actor)
        team = next((team for team in await self.store.teams(organization.id) if team.id == team_id), None)
        if team is None:
            raise HTTPException(status_code=404, detail="Team not found")
        return team

    async def set_team_member(self, name: str, team_id: uuid.UUID, user_id: uuid.UUID, actor: User) -> None:
        """Add an organization member to one of its teams."""
        team = await self.team(name, team_id, actor)
        if not any(member.user_id == user_id for member in await self.store.members(team.organization_id)):
            raise HTTPException(status_code=400, detail="Team members must belong to the organization")
        if not any(member.user_id == user_id for member in await self.store.team_members(team.id)):
            await self.store.save(TeamMember(team_id=team.id, user_id=user_id))

    async def set_collaborator(
        self, repository: Repository, body: CollaboratorInput, actor: User
    ) -> RepositoryCollaborator:
        """Grant a scoped role; only owners can grant or change an owner role."""
        await self.require(repository, actor, "repository:admin")
        if body.user_id is not None and await self.users.find(body.user_id) is None:
            raise HTTPException(status_code=404, detail="User not found")
        if body.team_id is not None and not any(
            team.id == body.team_id for team in await self.store.teams(repository.owner_id)
        ):
            raise HTTPException(status_code=400, detail="Team must belong to the repository's organization")
        existing = next(
            (
                item
                for item in await self.store.collaborators(repository.id)
                if item.user_id == body.user_id and item.team_id == body.team_id
            ),
            None,
        )
        if body.role == RepositoryRole.OWNER or (existing is not None and existing.role == RepositoryRole.OWNER):
            await self.require(repository, actor, "repository:owner")
        collaborator = existing or RepositoryCollaborator(
            repository_id=repository.id, user_id=body.user_id, team_id=body.team_id
        )
        collaborator.role = body.role
        await self.store.save(collaborator)
        return collaborator

    async def remove_collaborator(self, repository: Repository, collaborator_id: uuid.UUID, actor: User) -> None:
        """Revoke a collaborator without allowing admins to revoke owners."""
        await self.require(repository, actor, "repository:admin")
        collaborator = next(
            (item for item in await self.store.collaborators(repository.id) if item.id == collaborator_id), None
        )
        if collaborator is None:
            raise HTTPException(status_code=404, detail="Collaborator not found")
        if collaborator.role == RepositoryRole.OWNER:
            await self.require(repository, actor, "repository:owner")
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
        )
