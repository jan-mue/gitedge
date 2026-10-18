import asyncio
import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.schemas.actions_cache import CacheIdentity
from app.services.actions.cache import CHUNK_SIZE, STATE_LIMIT, ActionsCacheService
from tests.unit.utils.actions import FakeActionsCacheStore
from tests.unit.utils.fakes import FakeCacheClient


async def test_parallel_caches_are_immutable_scoped_and_survive_fresh_services() -> None:
    store, cache = FakeActionsCacheStore(), FakeCacheClient()
    first, other = uuid.uuid4(), uuid.uuid4()
    service = ActionsCacheService(store, cache)
    identities = [CacheIdentity(key=key, version="v1") for key in ["linux-python", "linux-bun"]]
    entries = await asyncio.gather(*(service.save(first, identity, identity.key.encode()) for identity in identities))
    service = ActionsCacheService(store, cache)
    for identity, entry in zip(identities, entries, strict=True):
        assert await service.lookup(first, identity, []) == entry
        assert await service.download(first, entry.id) == identity.key.encode()
        assert await service.download(other, entry.id) is None
        assert await service.lookup(other, identity, []) is None
        assert await service.lookup(first, CacheIdentity(key=identity.key, version="v2"), []) is None
        assert await service.save(first, identity, b"attempted overwrite") == entry
        assert await service.download(first, entry.id) == identity.key.encode()
    assert await service.lookup(first, CacheIdentity(key="missing", version="v1"), ["linux-py", "linux-"]) == entries[0]


async def test_evicted_corrupt_and_expired_generations_are_misses_and_can_be_replaced() -> None:
    store, cache = FakeActionsCacheStore(), FakeCacheClient()
    service, repository = ActionsCacheService(store, cache), uuid.uuid4()
    identity = CacheIdentity(key="cache", version="v1")
    old = await service.save(repository, identity, b"original")
    cache.values.clear()
    assert await service.lookup(repository, identity, []) is None
    new = await service.save(repository, identity, b"replaced")
    assert old.id != new.id
    assert await service.download(repository, old.id) is None
    assert await service.download(repository, new.id) == b"replaced"
    cache.values[(f"actions:{repository}", f"{new.id}:0")] = "not valid base64"
    assert await service.lookup(repository, identity, []) is None
    latest = await service.save(repository, identity, b"latest")
    store.entries[(repository, identity.key, identity.version)].expires_at = datetime.now(UTC) - timedelta(seconds=1)
    assert await service.lookup(repository, identity, []) is None
    assert await service.download(repository, latest.id) is None


async def test_cache_chunks_fit_vercel_limits_and_missing_chunks_do_not_return_partial_data() -> None:
    store, cache = FakeActionsCacheStore(), FakeCacheClient()
    service, repository = ActionsCacheService(store, cache), uuid.uuid4()
    identity = CacheIdentity(key="large", version="v1")
    payload = b"a" * (CHUNK_SIZE * 2 + 11)
    entry = await service.save(repository, identity, payload)
    assert len(cache.values) == 3
    assert all(len(value.encode()) < 512 * 1024 for value in cache.values.values())
    assert await service.download(repository, entry.id) == payload
    del cache.values[(f"actions:{repository}", f"{entry.id}:1")]
    assert await service.download(repository, entry.id) is None
    assert await service.lookup(repository, identity, []) is None
    with pytest.raises(ValueError, match="32 MiB"):
        await service.save(repository, identity, b"x" * (STATE_LIMIT + 1))


async def test_concurrent_same_key_writers_publish_one_complete_generation() -> None:
    store, cache = FakeActionsCacheStore(), FakeCacheClient()
    service, repository = ActionsCacheService(store, cache), uuid.uuid4()
    identity = CacheIdentity(key="shared", version="v1")
    entries = await asyncio.gather(*(service.save(repository, identity, value * CHUNK_SIZE) for value in [b"a", b"b"]))
    assert entries[0].id == entries[1].id
    assert await service.download(repository, entries[0].id) in [b"a" * CHUNK_SIZE, b"b" * CHUNK_SIZE]
    await service.delete_repository(repository)
    assert await service.lookup(repository, identity, []) is None
