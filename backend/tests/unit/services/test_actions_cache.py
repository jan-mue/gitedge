import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import pytest

from app.schemas.actions_cache import CacheIdentity
from app.services.actions.cache import STATE_LIMIT, ActionsCacheService
from app.services.actions.service import ActionsService
from tests.unit.utils.actions import FakeActionsQueue, FakeActionsStore, FakeWorkflowCompiler
from tests.unit.utils.fakes import FakeActionsCacheStore, FakeBlobStorageClient

if TYPE_CHECKING:
    from pytest_mock import MockerFixture


async def test_parallel_caches_are_immutable_scoped_and_survive_fresh_services() -> None:
    store, blobs = FakeActionsCacheStore(), FakeBlobStorageClient()
    first, other = uuid.uuid4(), uuid.uuid4()
    service = ActionsCacheService(store, blobs)
    identities = [CacheIdentity(key=key, version="v1") for key in ["linux-python", "linux-bun"]]
    entries = await asyncio.gather(*(service.save(first, identity, identity.key.encode()) for identity in identities))
    service = ActionsCacheService(store, blobs)
    assert len(blobs.objects) == 2
    assert all(key.startswith(f"actions/{first}/cache/") for key in blobs.objects)
    for identity, entry in zip(identities, entries, strict=True):
        assert await service.lookup(first, identity, []) == entry
        assert await service.download(first, entry.id) == identity.key.encode()
        assert await service.download(other, entry.id) is None
        assert await service.lookup(other, identity, []) is None
        assert await service.lookup(first, CacheIdentity(key=identity.key, version="v2"), []) is None
        assert await service.save(first, identity, b"attempted overwrite") == entry
        assert await service.download(first, entry.id) == identity.key.encode()
    assert await service.lookup(first, CacheIdentity(key="missing", version="v1"), ["linux-py", "linux-"]) == entries[0]


async def test_missing_corrupt_and_expired_archives_are_misses_and_can_be_replaced() -> None:
    store, blobs = FakeActionsCacheStore(), FakeBlobStorageClient()
    service, repository = ActionsCacheService(store, blobs), uuid.uuid4()
    identity = CacheIdentity(key="cache", version="v1")
    old = await service.save(repository, identity, b"original")
    blobs.objects.clear()
    assert await service.lookup(repository, identity, []) is None
    new = await service.save(repository, identity, b"replaced")
    assert old.id != new.id
    assert await service.download(repository, old.id) is None
    assert await service.download(repository, new.id) == b"replaced"
    blobs.objects[next(iter(blobs.objects))] = b"corrupted"
    assert await service.lookup(repository, identity, []) is None
    latest = await service.save(repository, identity, b"latest")
    assert len(blobs.objects) == 1
    assert await service.download(repository, latest.id) == b"latest"
    store.entries[(repository, identity.key, identity.version)].expires_at = datetime.now(UTC) - timedelta(seconds=1)
    assert await service.lookup(repository, identity, []) is None
    assert await service.download(repository, latest.id) is None
    assert not blobs.objects
    replacement = await service.save(repository, identity, b"after expiry")
    assert await service.download(repository, replacement.id) == b"after expiry"


async def test_cache_archives_are_stored_intact_with_size_and_checksum_validation() -> None:
    store, blobs = FakeActionsCacheStore(), FakeBlobStorageClient()
    service, repository = ActionsCacheService(store, blobs), uuid.uuid4()
    identity = CacheIdentity(key="large", version="v1")
    payload = b"a" * (1024 * 1024 + 11)
    entry = await service.save(repository, identity, payload)
    key = next(iter(blobs.objects))
    assert blobs.objects[key] == payload
    assert await service.download(repository, entry.id) == payload
    blobs.objects[key] = b"b" * len(payload)
    assert await service.download(repository, entry.id) is None
    assert await service.lookup(repository, identity, []) is None
    with pytest.raises(ValueError, match="32 MiB"):
        await service.save(repository, identity, b"x" * (STATE_LIMIT + 1))


async def test_concurrent_same_key_writers_keep_only_the_published_archive(mocker: MockerFixture) -> None:
    store, blobs = FakeActionsCacheStore(), FakeBlobStorageClient()
    service, repository = ActionsCacheService(store, blobs), uuid.uuid4()
    identity = CacheIdentity(key="shared", version="v1")
    uploaded = asyncio.Event()
    original_put = blobs.put

    async def put(key: str, payload: bytes) -> None:
        await original_put(key, payload)
        if len(blobs.objects) == 2:
            uploaded.set()
        await asyncio.wait_for(uploaded.wait(), timeout=1)

    mocker.patch.object(blobs, "put", side_effect=put)
    entries = await asyncio.gather(*(service.save(repository, identity, value * 1024) for value in [b"a", b"b"]))
    assert entries[0].id == entries[1].id
    assert len(blobs.objects) == 1
    assert await service.download(repository, entries[0].id) in [b"a" * 1024, b"b" * 1024]


async def test_repository_deletion_removes_cache_archives_and_preserves_other_repositories(
    mocker: MockerFixture,
) -> None:
    store, blobs = FakeActionsCacheStore(), FakeBlobStorageClient()
    service = ActionsCacheService(store, blobs)
    repository, other = uuid.uuid4(), uuid.uuid4()
    identity = CacheIdentity(key="cache", version="v1")
    await service.save(repository, identity, b"cache contents")
    preserved = await service.save(other, identity, b"other repository")
    actions = ActionsService(
        FakeActionsStore(),
        mocker.Mock(),
        mocker.Mock(),
        blobs,
        mocker.AsyncMock(),
        compiler=FakeWorkflowCompiler(),
        queue=FakeActionsQueue(),
        provider="docker",
        max_timeout=60,
        max_parallel=1,
        cache=service,
    )
    await actions.delete_repository_blobs(repository)
    assert await service.lookup(repository, identity, []) is None
    assert await service.download(other, preserved.id) == b"other repository"
    assert len(blobs.objects) == 1
