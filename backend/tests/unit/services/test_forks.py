from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException

from app.entities.repositories import Repository
from app.entities.users import User
from app.schemas.social import ForkCreate
from app.services.activity import ActivityService
from app.services.blob_backend import BlobBackend
from app.services.forks import ForkService
from app.services.repositories import RepositoryService
from tests.unit.utils.fakes import (
    FakeActivityStore,
    FakeBlobStorageClient,
    FakeOrganizationStore,
    FakeRedisClient,
    FakeRepositoryStore,
    FakeStarStore,
    FakeUserStore,
)


def _setup() -> tuple[FakeRepositoryStore, FakeUserStore, User, User, ForkService, RepositoryService]:
    users = FakeUserStore()
    organizations = FakeOrganizationStore()
    repository_store = FakeRepositoryStore(users, organizations)
    star_store = FakeStarStore()
    activity_store = FakeActivityStore()

    owner = User(name="owner", lower_name="owner", email="owner@example.com", hashed_password="x")
    owner.id = uuid.uuid4()
    users.persist(owner)

    alice = User(name="alice", lower_name="alice", email="alice@example.com", hashed_password="x")
    alice.id = uuid.uuid4()
    users.persist(alice)

    activity_service = ActivityService(activity_store, repository_store, star_store)
    repository_service = RepositoryService(
        BlobBackend(), FakeBlobStorageClient(), FakeRedisClient(), repository_store, star_store
    )
    fork_service = ForkService(repository_store, repository_service, activity_service, star_store)
    return repository_store, users, owner, alice, fork_service, repository_service


async def test_fork_repository() -> None:
    repository_store, _users, owner, alice, fork_service, repository_service = _setup()

    source = Repository(name="repo", owner_id=owner.id)
    await repository_store.add(source)

    fork = await fork_service.fork("owner", "repo", ForkCreate(), alice)

    assert fork.name == "repo"
    assert fork.owner == "alice"
    assert repository_service.backend.repository_exists("alice/repo.git")

    assert await repository_store.count_by_fork_of(source.id) == 1
    assert fork.forks_count == 0

    forks = await fork_service.list_forks("owner", "repo")
    assert forks.count == 1
    assert forks.data[0].owner == "alice"


async def test_fork_repository_with_name_collision() -> None:
    repository_store, _users, owner, alice, fork_service, _repository_service = _setup()

    source = Repository(name="repo", owner_id=owner.id)
    await repository_store.add(source)
    existing = Repository(name="repo", owner_id=alice.id)
    await repository_store.add(existing)

    with pytest.raises(HTTPException) as exc_info:
        await fork_service.fork("owner", "repo", ForkCreate(), alice)

    assert exc_info.value.status_code == 409
