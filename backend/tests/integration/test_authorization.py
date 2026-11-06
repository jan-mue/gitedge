"""Verify authorization facts, transactions, and revocation against PostgreSQL."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import create_async_engine

from app.clients.authorization import SQLAuthorizationStore
from app.clients.database import create_session_factory
from app.clients.organizations import SQLOrganizationStore
from app.clients.repositories import SQLRepositoryStore
from app.clients.users import SQLUserStore
from app.entities.organizations import Organization
from app.entities.repositories import Repository
from app.entities.users import User
from app.permissions import repository_visibility
from app.schemas.authorization import CollaboratorInput, RepositoryCollaborator, RepositoryRole, TeamMember
from app.services.authorization import AuthorizationService
from tests.conftest import _run_async

if TYPE_CHECKING:
    from pytest_mock import MockerFixture
    from sqlalchemy.ext.asyncio import AsyncSession


def test_authorization_persistence(infrastructure: dict[str, str], mocker: MockerFixture) -> None:
    _run_async(check_authorization_persistence(infrastructure["DATABASE_URL"], mocker))


async def check_authorization_persistence(database_url: str, mocker: MockerFixture) -> None:
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
                display_name=f"Display {suffix}",
                name=f"member-{suffix}",
                lower_name=f"member-{suffix}",
                email=f"member-{suffix}@example.com",
                hashed_password="unused",
                is_active=True,
            )
            await users.add(admin)
            await users.add(member)
            for query in [member.name.upper(), member.email, f"Display {suffix}"]:
                assert [candidate.id for candidate in await users.search(query)] == [member.id]
            assert not await users.search("%")
            assert not await users.search("_")
            organization = Organization(name=f"org-{suffix}", lower_name=f"org-{suffix}")
            await facts.create_organization(organization, admin.id)
            assert (await facts.members(organization.id))[0].is_admin
            repository = Repository(name="private", owner_id=organization.id, is_private=True)
            await repositories.add(repository)
            await authorization.set_member(organization.name, member.id, False, admin)
            team = await authorization.create_team(organization.name, "developers", admin)
            await authorization.set_team_member(organization.name, team.id, member.id, admin)
            await authorization.set_team_member(organization.name, team.id, admin.id, admin)
            grant = await authorization.set_collaborator(
                repository, CollaboratorInput(team_id=team.id, role=RepositoryRole.WRITE), admin
            )
            grant_id = grant.id
            repository_id = repository.id
            await db.reset()
            repository = await repositories.get(repository_id)
            assert await authorization.can(repository, member, "git:write")
            candidates = [admin, member] + [
                User(id=uuid.uuid4(), name=f"outsider-{index}", is_active=True) for index in range(500)
            ]
            query = mocker.spy(db, "execute")
            try:
                assert await authorization.visible_users(repository, candidates) == [admin, member]
                query.assert_awaited_once()
            finally:
                mocker.stop(query)
            await check_batched_repository_roles(db, authorization, repository, admin, member, team.id, mocker)
            await repositories.update(repository, {"name": "renamed"})
            assert await authorization.can(repository, member, "git:write")
            await authorization.remove_member(organization.name, member.id, admin)
            assert [item.user_id for item in await facts.team_members(team.id)] == [admin.id]
            stale_team_member = TeamMember(team_id=team.id, user_id=member.id)
            await facts.save(stale_team_member)
            assert not await authorization.can(repository, member)
            assert await authorization.visible_users(repository, [admin, member]) == [admin]
            await facts.remove(stale_team_member)
            assert not await authorization.can(repository, member)
            await authorization.set_member(organization.name, member.id, False, admin)
            assert not await authorization.can(repository, member)
            await authorization.set_team_member(organization.name, team.id, member.id, admin)
            assert await authorization.can(repository, member, "git:write")
            team = await authorization.team(organization.name, team.id, admin)
            await facts.remove(team)
            assert not any(item.id == grant_id for item in await facts.collaborators(repository_id))
            assert not await facts.team_members(team.id)
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


async def check_batched_repository_roles(
    db: AsyncSession,
    authorization: AuthorizationService,
    repository: Repository,
    admin: User,
    member: User,
    team_id: uuid.UUID,
    mocker: MockerFixture,
) -> None:
    """A 10k-row batch uses one query and preserves all grant scope boundaries."""
    suffix = uuid.uuid4().hex
    other_org = Organization(name=f"other-{suffix}", lower_name=f"other-{suffix}")
    await authorization.store.create_organization(other_org, admin.id)
    sibling = Repository(name="sibling", owner_id=repository.owner_id, is_private=True)
    direct = Repository(name=f"direct-{suffix}", owner_id=admin.id, is_private=True)
    foreign = Repository(name="foreign", owner_id=other_org.id, is_private=True)
    db.add_all([sibling, direct, foreign])
    await db.commit()
    await authorization.store.save(RepositoryCollaborator(repository_id=direct.id, user_id=member.id, role="read"))
    # A corrupt cross-organization team grant must still fail closed at read time.
    await authorization.store.save(RepositoryCollaborator(repository_id=foreign.id, team_id=team_id, role="write"))
    assert await authorization.visible_users(foreign, [admin, member]) == [admin]
    candidates = [repository, sibling, direct, foreign] + [
        Repository(id=uuid.uuid4(), name=f"candidate-{index}", owner_id=other_org.id, is_private=True)
        for index in range(9996)
    ]
    query = mocker.spy(db, "execute")
    try:
        visible = await authorization.visible_repositories(candidates, member)
        assert {item.id for item in visible} == {repository.id, direct.id}
        query.assert_awaited_once()
    finally:
        mocker.stop(query)
    # SQL pagination/counting must preserve the same relationship graph as Casbin.
    parent = Repository(name=f"fork-parent-{suffix}", owner_id=admin.id, is_private=True)
    await authorization.repositories.add(parent)
    for candidate in [repository, sibling, direct, foreign]:
        await authorization.repositories.update(candidate, {"fork_of_id": parent.id})
    assert (
        await authorization.repositories.count_by_fork_of(parent.id, visibility=await repository_visibility(member))
        == 2
    )
    assert (
        await authorization.repositories.count_by_fork_of(parent.id, visibility=await repository_visibility(admin)) == 4
    )
    assert (
        await authorization.repositories.count_by_fork_of(parent.id, visibility=await repository_visibility(None)) == 0
    )
    page = await authorization.repositories.list_by_fork_of(
        parent.id, limit=1, visibility=await repository_visibility(member)
    )
    assert len(page) == 1
    assert page[0].id in {repository.id, direct.id}
    assert not await authorization.repositories.list_by_fork_of(
        parent.id, offset=2, limit=1, visibility=await repository_visibility(member)
    )
    await authorization.repositories.delete(parent)
    # Organization administration remains scoped to the owning organization.
    for candidate in [repository, sibling, direct, foreign]:
        assert await authorization.can(candidate, admin, "repository:delete")
    permissions = await authorization.permissions(repository, member)
    assert permissions.model_dump() == {"read": True, "write": True, "admin": False, "owner": False}
    await authorization.repositories.delete(sibling)
    await authorization.repositories.delete(direct)
    await authorization.repositories.delete(foreign)
    await authorization.organizations.delete(other_org)
