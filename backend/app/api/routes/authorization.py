"""Organization membership, teams, and repository collaborator settings."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies import AuthorizationServiceDep, CurrentUser, OptionalUser, require_repository
from app.entities.repositories import Repository
from app.schemas.authorization import (
    CollaboratorInput,
    CollaboratorPublic,
    MemberInput,
    MemberPublic,
    RepositoryPermissions,
    TeamInput,
    TeamPublic,
)

router = APIRouter(tags=["authorization"])
AdminRepository = Annotated[Repository, Depends(require_repository("repository:admin"))]
ReadableRepository = Annotated[Repository, Depends(require_repository())]


@router.get("/repositories/{owner}/{repo}/permissions")  # noqa: FAST003 -- path resolved by permission dependency
async def get_permissions(
    repository: ReadableRepository, authorization: AuthorizationServiceDep, user: OptionalUser
) -> RepositoryPermissions:
    """Return effective permissions for the current viewer."""
    return RepositoryPermissions(
        **{
            permission: await authorization.can(repository, user, f"repository:{permission}")
            for permission in ("read", "write", "admin", "owner")
        }
    )


@router.get("/repositories/{owner}/{repo}/collaborator-teams")  # noqa: FAST003 -- path resolved by permission dependency
async def list_collaborator_teams(
    repository: AdminRepository, authorization: AuthorizationServiceDep
) -> list[TeamPublic]:
    """List teams eligible for grants on this repository."""
    return [TeamPublic.model_validate(team) for team in await authorization.store.teams(repository.owner_id)]


@router.get("/organizations/{organization}/members")
async def list_members(
    organization: str, authorization: AuthorizationServiceDep, user: CurrentUser
) -> list[MemberPublic]:
    """List an organization's members."""
    org = await authorization.organization(organization, user, "organization:read")
    return [MemberPublic.model_validate(member) for member in await authorization.store.members(org.id)]


@router.put("/organizations/{organization}/members/{user_id}")
async def set_member(
    organization: str, user_id: uuid.UUID, body: MemberInput, authorization: AuthorizationServiceDep, user: CurrentUser
) -> MemberPublic:
    """Add a member or change their organization role."""
    return MemberPublic.model_validate(await authorization.set_member(organization, user_id, body.is_admin, user))


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
        raise HTTPException(status_code=404, detail="Team member not found")
    await authorization.store.remove(member)


@router.get("/repositories/{owner}/{repo}/collaborators")  # noqa: FAST003 -- path resolved by permission dependency
async def list_collaborators(
    repository: AdminRepository, authorization: AuthorizationServiceDep
) -> list[CollaboratorPublic]:
    """List explicit repository collaborators."""
    return [
        await authorization.collaborator_public(repository, item)
        for item in await authorization.store.collaborators(repository.id)
    ]


@router.put("/repositories/{owner}/{repo}/collaborators")  # noqa: FAST003 -- path resolved by permission dependency
async def set_collaborator(
    repository: AdminRepository, body: CollaboratorInput, authorization: AuthorizationServiceDep, user: CurrentUser
) -> CollaboratorPublic:
    """Add or update a user or team's repository role."""
    return await authorization.collaborator_public(
        repository, await authorization.set_collaborator(repository, body, user)
    )


@router.delete("/repositories/{owner}/{repo}/collaborators/{collaborator_id}", status_code=204)  # noqa: FAST003 -- path resolved by permission dependency
async def remove_collaborator(
    repository: AdminRepository, collaborator_id: uuid.UUID, authorization: AuthorizationServiceDep, user: CurrentUser
) -> None:
    """Revoke an explicit repository role."""
    await authorization.remove_collaborator(repository, collaborator_id, user)
