from __future__ import annotations

import uuid

import pytest
from dulwich.objects import Blob, Commit, Tree
from dulwich.refs import Ref
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
    FakeCacheClient,
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
        BlobBackend(), FakeBlobStorageClient(), FakeRedisClient(), FakeCacheClient(), repository_store, star_store
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


async def test_fork_repository_into_same_owner() -> None:
    repository_store, _users, owner, _alice, fork_service, _repository_service = _setup()

    source = Repository(name="repo", owner_id=owner.id)
    await repository_store.add(source)

    with pytest.raises(HTTPException) as exc_info:
        await fork_service.fork("owner", "repo", ForkCreate(name="repo-fork"), owner)

    assert exc_info.value.status_code == 400


async def test_fork_copies_persisted_objects_and_refs() -> None:
    repository_store, _users, owner, alice, fork_service, repository_service = _setup()
    await repository_store.add(Repository(name="repo", owner_id=owner.id))
    repo = await repository_service.load_repository("owner", "repo")
    blob = Blob.from_string(b"fork content\n")
    tree = Tree()
    tree.add(b"file.txt", 0o100644, blob.id)
    commit = Commit()
    commit.tree = tree.id
    commit.author = commit.committer = b"Owner <owner@example.com>"
    commit.author_time = commit.commit_time = 1_700_000_000
    commit.author_timezone = commit.commit_timezone = 0
    commit.message = b"Initial commit"
    repo.object_store.add_objects([(blob, None), (tree, None), (commit, None)])
    repo.refs.set_if_equals(Ref(b"refs/heads/main"), None, commit.id)
    await repository_service.save_changes("owner", "repo")
    await fork_service.fork("owner", "repo", ForkCreate(), alice)
    assert await repository_service.get_raw("alice", "repo", "main", "file.txt") == b"fork content\n"
    info = await repository_service.get_info("alice", "repo", "HEAD")
    assert info.last_commit is not None
    assert info.last_commit.sha == commit.id.decode()


async def test_fork_rejects_other_destination_owner() -> None:
    repository_store, users, owner, alice, fork_service, _repository_service = _setup()
    await repository_store.add(Repository(name="repo", owner_id=owner.id))
    bob = User(name="bob", lower_name="bob", email="bob@example.com", hashed_password="x")
    users.persist(bob)
    with pytest.raises(HTTPException) as error:
        await fork_service.fork("owner", "repo", ForkCreate(owner="bob"), alice)
    assert error.value.status_code == 403
    assert await repository_store.find_by_owner_and_name("bob", "repo") is None
