"""Verify authorization facts, transactions, and revocation against PostgreSQL."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine

from app.clients.authorization import SQLAuthorizationStore
from app.clients.database import create_session_factory
from app.clients.organizations import SQLOrganizationStore
from app.clients.repositories import SQLRepositoryStore
from app.clients.users import SQLUserStore
from app.entities.authorization import RepositoryCollaborator, TeamMember
from app.entities.organizations import Organization
from app.entities.repositories import Repository
from app.entities.users import User
from app.schemas.authorization import CollaboratorInput, RepositoryRole
from app.services.authorization import AuthorizationService
from tests.integration.conftest import _run_async


def test_authorization_persistence(infrastructure: dict[str, str]) -> None:
    _run_async(check_authorization_persistence(infrastructure["DATABASE_URL"]))


async def check_authorization_persistence(database_url: str) -> None:
    engine = create_async_engine(database_url)
    try:
        async with create_session_factory(engine)() as db:
            users = SQLUserStore(db)
            organizations = SQLOrganizationStore(db)
            repositories = SQLRepositoryStore(db)
            facts = SQLAuthorizationStore(db)
            authorization = AuthorizationService(facts, repositories, organizations, users)
            suffix = uuid.uuid4().hex
            admin = User(
                name=f"admin-{suffix}",
                lower_name=f"admin-{suffix}",
                email=f"admin-{suffix}@example.com",
                hashed_password="unused",
                is_active=True,
            )
            member = User(
                name=f"member-{suffix}",
                lower_name=f"member-{suffix}",
                email=f"member-{suffix}@example.com",
                hashed_password="unused",
                is_active=True,
            )
            await users.add(admin)
            await users.add(member)
            organization = Organization(name=f"org-{suffix}", lower_name=f"org-{suffix}")
            await facts.create_organization(organization, admin.id)
            assert (await facts.members(organization.id))[0].is_admin
            repository = Repository(name="private", owner_id=organization.id, is_private=True)
            await repositories.add(repository)
            await authorization.set_member(organization.name, member.id, False, admin)
            team = await authorization.create_team(organization.name, "developers", admin)
            await authorization.set_team_member(organization.name, team.id, member.id, admin)
            grant = await authorization.set_collaborator(
                repository, CollaboratorInput(team_id=team.id, role=RepositoryRole.WRITE), admin
            )
            grant_id = grant.id
            repository_id = repository.id
            await db.reset()
            repository = await repositories.get(repository_id)
            assert await authorization.can(repository, member, "repository:write")
            await repositories.update(repository, {"name": "renamed"})
            assert await authorization.can(repository, member, "repository:write")
            await authorization.remove_member(organization.name, member.id, admin)
            assert not await facts.team_members(team.id)
            assert not await authorization.can(repository, member)
            await authorization.set_member(organization.name, member.id, False, admin)
            assert not await authorization.can(repository, member)
            await authorization.set_team_member(organization.name, team.id, member.id, admin)
            assert await authorization.can(repository, member, "repository:write")
            team = await authorization.team(organization.name, team.id, admin)
            await facts.remove(team)
            assert await db.scalar(select(RepositoryCollaborator).where(RepositoryCollaborator.id == grant_id)) is None
            assert not list(await db.scalars(select(TeamMember).where(TeamMember.team_id == team.id)))
            assert not await authorization.can(repository, member)
            await authorization.set_collaborator(
                repository, CollaboratorInput(user_id=member.id, role=RepositoryRole.READ), admin
            )
            await repositories.delete(repository)
            assert not await facts.collaborators(repository_id)
            await organizations.delete(await organizations.get(organization.id))
            await users.delete(await users.get(member.id))
            await users.delete(await users.get(admin.id))
    finally:
        await engine.dispose()
