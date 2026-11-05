"""Repository selections constrain fork queries, pagination, and total counts."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import create_async_engine

from app.clients.authorization import SQLAuthorizationStore
from app.clients.database import create_session_factory
from app.clients.organizations import SQLOrganizationStore
from app.clients.repositories import SQLRepositoryStore
from app.clients.stars import SQLStarStore
from app.clients.users import SQLUserStore
from app.entities.authorization import RepositoryCollaborator
from app.entities.repositories import Repository
from app.entities.users import User
from app.services.activity import ActivityService
from app.services.authorization import AuthorizationService
from app.services.forks import ForkService
from app.services.repositories import RepositoryService
from tests.conftest import _run_async

if TYPE_CHECKING:
    from pytest_mock import MockerFixture


def test_scoped_fork_pagination(infrastructure: dict[str, str], mocker: MockerFixture) -> None:
    _run_async(check_scoped_fork_pagination(infrastructure["DATABASE_URL"], mocker))


async def check_scoped_fork_pagination(database_url: str, mocker: MockerFixture) -> None:
    engine = create_async_engine(database_url)
    try:
        async with create_session_factory(engine)() as db:
            users = SQLUserStore(db)
            repositories = SQLRepositoryStore(db)
            suffix = uuid.uuid4().hex
            owner = User(
                name=f"forks-{suffix}",
                lower_name=f"forks-{suffix}",
                email=f"{suffix}@example.com",
                hashed_password="unused",
                is_active=True,
            )
            await users.add(owner)
            source = Repository(name="source", owner_id=owner.id, is_private=True)
            await repositories.add(source)
            forks = []
            for index in range(5):
                fork = Repository(
                    name=f"fork-{index}",
                    owner_id=owner.id,
                    fork_of_id=source.id,
                    is_private=True,
                    created_at=datetime(2026, 1, 1, tzinfo=UTC) + timedelta(minutes=index),
                )
                await repositories.add(fork)
                forks.append(fork)
            allowed = [source.id, forks[1].id, forks[3].id]
            assert [fork.name for fork in await repositories.list_by_fork_of(source.id, limit=1)] == ["fork-4"]
            assert [
                fork.name
                for fork in await repositories.list_by_fork_of(
                    source.id, offset=1, limit=1, allowed_repository_ids=allowed
                )
            ] == ["fork-1"]
            assert not await repositories.list_by_fork_of(source.id, allowed_repository_ids=[])
            authorization = AuthorizationService(
                SQLAuthorizationStore(db), repositories, SQLOrganizationStore(db), users
            )
            service = ForkService(
                repositories,
                mocker.Mock(spec=RepositoryService),
                mocker.Mock(spec=ActivityService),
                SQLStarStore(db),
                authorization,
            )
            for offset, expected in [(0, ["fork-3"]), (1, ["fork-1"]), (2, [])]:
                page = await service.list_forks(
                    owner.name, source.name, offset, 1, owner, allowed_repository_ids=allowed
                )
                assert [fork.name for fork in page.data] == expected
                assert page.count == 2
            unrestricted = await service.list_forks(owner.name, source.name, limit=1, user=owner)
            assert unrestricted.count == 5
            assert [fork.name for fork in unrestricted.data] == ["fork-4"]
            empty = await service.list_forks(owner.name, source.name, user=owner, allowed_repository_ids=[])
            assert empty.count == 0
            assert not empty.data
            viewer = User(
                name=f"viewer-{suffix}",
                lower_name=f"viewer-{suffix}",
                email=f"viewer-{suffix}@example.com",
                hashed_password="unused",
                is_active=True,
            )
            await users.add(viewer)
            await repositories.update(forks[0], {"is_private": False})
            grants = [
                RepositoryCollaborator(repository_id=forks[index].id, user_id=viewer.id, role="read")
                for index in (1, 3)
            ]
            for grant in grants:
                await authorization.store.save(grant)
            for offset, expected in [(0, ["fork-3"]), (1, ["fork-1"]), (2, ["fork-0"]), (3, [])]:
                page = await service.list_forks(owner.name, source.name, offset, 1, viewer)
                assert [fork.name for fork in page.data] == expected
                assert page.count == 3
            zero_limit = await service.list_forks(owner.name, source.name, limit=0, user=viewer)
            assert not zero_limit.data
            assert zero_limit.count == 3
            selected = await service.list_forks(
                owner.name, source.name, limit=1, user=viewer, allowed_repository_ids=allowed
            )
            assert selected.count == 2
            assert [fork.name for fork in selected.data] == ["fork-3"]
            anonymous = await service.list_forks(owner.name, source.name)
            assert anonymous.count == 1
            assert [fork.name for fork in anonymous.data] == ["fork-0"]
            await authorization.store.remove(grants[1])
            revoked = await service.list_forks(owner.name, source.name, user=viewer, allowed_repository_ids=allowed)
            assert revoked.count == 1
            assert [fork.name for fork in revoked.data] == ["fork-1"]
            await users.update(viewer, {"is_active": False})
            inactive = await service.list_forks(owner.name, source.name, user=viewer)
            assert inactive.count == 0
            assert not inactive.data
            for fork in forks:
                await repositories.delete(fork)
            await repositories.delete(source)
            await users.delete(viewer)
            await users.delete(owner)
    finally:
        await engine.dispose()
