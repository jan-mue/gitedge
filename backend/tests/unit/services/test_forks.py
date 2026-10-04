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
    FakeRedisClient,
    FakeRepositoryStore,
    FakeStarStore,
    FakeUserStore,
)


async def test_fork_repository() -> None:
    repository_store = FakeRepositoryStore()
    user_store = FakeUserStore()
    star_store = FakeStarStore()
    activity_store = FakeActivityStore()

    activity_service = ActivityService(activity_store, repository_store, user_store, star_store)
    repository_service = RepositoryService(BlobBackend(), FakeBlobStorageClient(), FakeRedisClient(), repository_store)
    fork_service = ForkService(repository_store, repository_service, activity_service)

    source = Repository(name="repo", path="owner/repo.git")
    await repository_store.add(source)

    user = User(username="alice", email="alice@example.com", hashed_password="x")
    user.id = uuid.uuid4()
    await user_store.add(user)

    fork = await fork_service.fork("owner/repo", ForkCreate(), user)

    assert fork.path == "alice/repo.git"
    assert fork.owner == "alice"
    assert repository_service.backend.repository_exists("alice/repo.git")

    updated_source = await repository_store.get(source.id)
    assert updated_source is not None
    assert updated_source.forks_count == 1
    assert len(activity_store.items) == 1

    forks = await fork_service.list_forks("owner/repo")
    assert forks.count == 1
    assert forks.data[0].path == "alice/repo.git"


async def test_fork_repository_with_name_collision() -> None:
    repository_store = FakeRepositoryStore()
    user_store = FakeUserStore()
    activity_service = ActivityService(FakeActivityStore(), repository_store, user_store, FakeStarStore())
    repository_service = RepositoryService(BlobBackend(), FakeBlobStorageClient(), FakeRedisClient(), repository_store)
    fork_service = ForkService(repository_store, repository_service, activity_service)

    source = Repository(name="repo", path="owner/repo.git")
    await repository_store.add(source)
    existing = Repository(name="repo", path="alice/repo.git")
    await repository_store.add(existing)

    user = User(username="alice", email="alice@example.com", hashed_password="x")
    user.id = uuid.uuid4()
    await user_store.add(user)

    with pytest.raises(HTTPException) as exc_info:
        await fork_service.fork("owner/repo", ForkCreate(), user)

    assert exc_info.value.status_code == 409
