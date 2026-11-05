"""Organization membership, teams, and repository collaborator settings."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.dependencies import AuthorizationServiceDep, CurrentUser, OptionalUser
from app.api.permissions import require_permission
from app.entities.users import User
from app.exceptions import NotFoundError
from app.schemas.authorization import (
    CollaboratorInput,
    CollaboratorPublic,
    MemberInput,
    MemberPublic,
    OrganizationPermissions,
    RepositoryPermissions,
    TeamInput,
    TeamPublic,
)
from app.schemas.users import ProfilePublic

router = APIRouter(tags=["authorization"])


@router.get("/repositories/{owner}/{repo}/permissions")
async def get_permissions(
    owner: str,
    repo: str,
    authorization: AuthorizationServiceDep,
    current_user: Annotated[User | None, Depends(require_permission("repository:read", user_dep=OptionalUser))],
) -> RepositoryPermissions:
    """Return effective permissions for the current viewer."""
    repository = await authorization.repositories.get_by_owner_and_name(owner, repo)
    return RepositoryPermissions(
        **{
            permission: await authorization.can(repository, current_user, f"repository:{permission}")
            for permission in ("read", "write", "admin", "owner")
        }
    )


@router.get(
    "/repositories/{owner}/{repo}/collaborator-teams",
    dependencies=[Depends(require_permission("repository:admin", user_dep=OptionalUser))],
)
async def list_collaborator_teams(owner: str, repo: str, authorization: AuthorizationServiceDep) -> list[TeamPublic]:
    """List teams eligible for grants on this repository."""
    repository = await authorization.repositories.get_by_owner_and_name(owner, repo)
    return [TeamPublic.model_validate(team) for team in await authorization.store.teams(repository.owner_id)]


@router.get("/organizations/{organization}/members")
async def list_members(
    organization: str, authorization: AuthorizationServiceDep, user: CurrentUser
) -> list[MemberPublic]:
    """List an organization's members."""
    org = await authorization.organization(organization, user, "organization:read")
    return [await authorization.member_public(member) for member in await authorization.store.members(org.id)]


@router.put("/organizations/{organization}/members/{user_id}")
async def set_member(
    organization: str, user_id: uuid.UUID, body: MemberInput, authorization: AuthorizationServiceDep, user: CurrentUser
) -> MemberPublic:
    """Add a member or change their organization role."""
    return await authorization.member_public(await authorization.set_member(organization, user_id, body.is_admin, user))


@router.delete("/organizations/{organization}/members/{user_id}", status_code=204)
async def remove_member(
    organization: str, user_id: uuid.UUID, authorization: AuthorizationServiceDep, user: CurrentUser
) -> None:
    """Remove a member and revoke their team memberships."""
    await authorization.remove_member(organization, user_id, user)


@router.get("/organizations/{organization}/teams")
async def list_teams(organization: str, authorization: AuthorizationServiceDep, user: CurrentUser) -> list[TeamPublic]:
    """List teams in an organization."""
    org = await authorization.organization(organization, user, "organization:read")
    return [TeamPublic.model_validate(team) for team in await authorization.store.teams(org.id)]


@router.post("/organizations/{organization}/teams", status_code=201)
async def create_team(
    organization: str, body: TeamInput, authorization: AuthorizationServiceDep, user: CurrentUser
) -> TeamPublic:
    """Create an organization team."""
    return TeamPublic.model_validate(await authorization.create_team(organization, body.name, user))


@router.delete("/organizations/{organization}/teams/{team_id}", status_code=204)
async def delete_team(
    organization: str, team_id: uuid.UUID, authorization: AuthorizationServiceDep, user: CurrentUser
) -> None:
    """Delete a team and its memberships and grants."""
    await authorization.store.remove(await authorization.team(organization, team_id, user))


@router.get("/organizations/{organization}/teams/{team_id}/members")
async def list_team_members(
    organization: str, team_id: uuid.UUID, authorization: AuthorizationServiceDep, user: CurrentUser
) -> list[uuid.UUID]:
    """List a team's member IDs."""
    team = await authorization.team(organization, team_id, user)
    return [member.user_id for member in await authorization.store.team_members(team.id)]


@router.put("/organizations/{organization}/teams/{team_id}/members/{user_id}", status_code=204)
async def set_team_member(
    organization: str, team_id: uuid.UUID, user_id: uuid.UUID, authorization: AuthorizationServiceDep, user: CurrentUser
) -> None:
    """Add an existing organization member to a team."""
    await authorization.set_team_member(organization, team_id, user_id, user)


@router.delete("/organizations/{organization}/teams/{team_id}/members/{user_id}", status_code=204)
async def remove_team_member(
    organization: str, team_id: uuid.UUID, user_id: uuid.UUID, authorization: AuthorizationServiceDep, user: CurrentUser
) -> None:
    """Remove a team membership."""
    team = await authorization.team(organization, team_id, user)
    member = next(
        (member for member in await authorization.store.team_members(team.id) if member.user_id == user_id), None
    )
    if member is None:
        raise NotFoundError(detail="Team member not found")
    await authorization.store.remove(member)


@router.get(
    "/repositories/{owner}/{repo}/collaborators",
    dependencies=[Depends(require_permission("repository:admin", user_dep=OptionalUser))],
)
async def list_collaborators(owner: str, repo: str, authorization: AuthorizationServiceDep) -> list[CollaboratorPublic]:
    """List explicit repository collaborators."""
    repository = await authorization.repositories.get_by_owner_and_name(owner, repo)
    return [
        await authorization.collaborator_public(repository, item)
        for item in await authorization.store.collaborators(repository.id)
    ]


@router.put("/repositories/{owner}/{repo}/collaborators")
async def set_collaborator(
    owner: str,
    repo: str,
    body: CollaboratorInput,
    authorization: AuthorizationServiceDep,
    current_user: Annotated[User, Depends(require_permission("repository:admin", user_dep=CurrentUser))],
) -> CollaboratorPublic:
    """Add or update a user or team's repository role."""
    repository = await authorization.repositories.get_by_owner_and_name(owner, repo)
    return await authorization.collaborator_public(
        repository, await authorization.set_collaborator(repository, body, current_user)
    )


@router.delete("/repositories/{owner}/{repo}/collaborators/{collaborator_id}", status_code=204)
async def remove_collaborator(
    owner: str,
    repo: str,
    collaborator_id: uuid.UUID,
    authorization: AuthorizationServiceDep,
    current_user: Annotated[User, Depends(require_permission("repository:admin", user_dep=CurrentUser))],
) -> None:
    """Revoke an explicit repository role."""
    repository = await authorization.repositories.get_by_owner_and_name(owner, repo)
    await authorization.remove_collaborator(repository, collaborator_id, current_user)


@router.get("/repositories/{owner}/{repo}/collaborator-candidates")
async def search_collaborator_candidates(
    owner: str,
    repo: str,
    authorization: AuthorizationServiceDep,
    user: Annotated[User, Depends(require_permission("repository:admin", user_dep=CurrentUser))],
    q: Annotated[str, Query(min_length=1, max_length=255)],
) -> list[ProfilePublic]:
    """Search public identities for the repository's add-people dialog."""
    del owner, repo, user
    return [ProfilePublic.model_validate(user) for user in await authorization.users.search(q)]


@router.get("/organizations/{organization}/member-candidates")
async def search_member_candidates(
    organization: str,
    authorization: AuthorizationServiceDep,
    user: CurrentUser,
    q: Annotated[str, Query(min_length=1, max_length=255)],
) -> list[ProfilePublic]:
    """Allow organization administrators to find users to add."""
    await authorization.organization(organization, user)
    return [ProfilePublic.model_validate(candidate) for candidate in await authorization.users.search(q)]


@router.get("/organizations/{organization}/permissions")
async def get_organization_permissions(
    organization: str,
    authorization: AuthorizationServiceDep,
    user: CurrentUser,
) -> OrganizationPermissions:
    """Expose management controls only to organization administrators."""
    org = await authorization.organization(organization, user, "organization:read")
    members = await authorization.store.members(org.id)
    return OrganizationPermissions(
        admin=user.is_superuser or any(member.user_id == user.id and member.is_admin for member in members)
    )
