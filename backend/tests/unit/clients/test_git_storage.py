"""Operation budgets and publication safety for both S3 and Vercel Blob storage."""

import asyncio
import json
from typing import TYPE_CHECKING, BinaryIO

import pytest
from dulwich.objects import Blob

from app.clients.git import CATALOG, GitStore
from app.services.git.repository import BlobObjectStore
from tests.unit.utils.fakes import FakeBlobStorageClient, FakeRedisClient
from tests.unit.utils.git import PackContents

if TYPE_CHECKING:
    from pytest_mock import MockerFixture

    from app.types import RepositoryChanges

PATH = "owner/repo.git"
PACK = PackContents(pack=b"pack", index=b"index")


async def test_legacy_catalog_lists_once_and_ignores_incomplete_pairs(mocker: MockerFixture) -> None:
    blob, redis = FakeBlobStorageClient(), FakeRedisClient()
    blob.put(f"{PATH}/packs/complete.pack", PACK.pack)
    blob.put(f"{PATH}/packs/complete.idx", PACK.index)
    blob.put(f"{PATH}/packs/orphan.pack", b"partial")
    listing = mocker.spy(blob, "list_keys")
    first, _ = await GitStore(blob, redis).load(PATH)
    second, _ = await GitStore(blob, redis).load(PATH)
    assert first == second == {"complete"}
    assert listing.call_count == 1
    assert json.loads(redis.values[f"{PATH}/{CATALOG}"]) == ["complete"]


async def test_retry_skips_existing_uploads_and_ref_only_writes_do_not_list(mocker: MockerFixture) -> None:
    blob, redis = FakeBlobStorageClient(), FakeRedisClient()
    storage = GitStore(blob, redis)
    await storage.load(PATH)
    for name in ("one", "two"):
        blob.put(f"{PATH}/packs/{name}.pack", PACK.pack)
        blob.put(f"{PATH}/packs/{name}.idx", PACK.index)
    listing, put = mocker.spy(blob, "list_keys"), mocker.spy(blob, "put")
    changes: RepositoryChanges = {"pack_additions": {"one"}, "ref_puts": {b"refs/heads/main": b"1" * 40}}
    await storage.save(PATH, changes)
    await storage.save(PATH, changes)
    await storage.save(PATH, {"ref_puts": {b"refs/heads/main": b"2" * 40}})
    assert put.call_count == 0
    assert listing.call_count == 0
    _, refs = await GitStore(blob, redis).load(PATH)
    assert refs["refs/heads/main"] == b"2" * 40
    assert listing.call_count == 0


async def test_failed_index_upload_never_publishes_catalog_or_refs(mocker: MockerFixture) -> None:
    blob, redis = FakeBlobStorageClient(), FakeRedisClient()
    storage = GitStore(blob, redis)
    names, _ = await storage.load(PATH)
    objects = BlobObjectStore(blob, f"{PATH}/packs/", names)
    original_put = blob.put

    def fail_index(key: str, data: bytes | BinaryIO) -> None:
        if key.endswith(".idx"):
            raise OSError("Interrupted upload")
        original_put(key, data)

    mocker.patch.object(blob, "put", side_effect=fail_index)
    with pytest.raises(OSError, match="Interrupted upload"):
        objects.add_objects([(Blob.from_string(b"new"), None)])
    assert not objects.pending_additions
    assert json.loads(redis.values[f"{PATH}/{CATALOG}"]) == []
    assert f"{PATH}/refs/refs/heads/main" not in redis.values
    mocker.patch.object(blob, "put", side_effect=original_put)
    objects.add_objects([(Blob.from_string(b"new"), None)])
    await storage.save(PATH, {"pack_additions": objects.pending_additions})
    assert (await storage.load(PATH))[0] == objects.names
    objects.close()


async def test_concurrent_writers_retain_both_packs_after_cas_retry(mocker: MockerFixture) -> None:
    blob, redis = FakeBlobStorageClient(), FakeRedisClient()
    storage = GitStore(blob, redis)
    await storage.load(PATH)
    for name in ("one", "two"):
        blob.put(f"{PATH}/packs/{name}.pack", PACK.pack)
        blob.put(f"{PATH}/packs/{name}.idx", PACK.index)
    await storage.load(PATH)
    original_cas = redis.compare_and_set
    conflicts = 0

    async def delayed_cas(expected: dict[str, str | None], updates: dict[str, str | None]) -> bool:
        nonlocal conflicts
        await asyncio.sleep(0)
        result = await original_cas(expected, updates)
        conflicts += not result
        return result

    mocker.patch.object(redis, "compare_and_set", side_effect=delayed_cas)
    await asyncio.gather(
        storage.save(PATH, {"pack_additions": {"one"}}),
        GitStore(blob, redis).save(PATH, {"pack_additions": {"two"}}),
    )
    assert conflicts >= 1
    packs, _ = await storage.load(PATH)
    assert set(packs) == {"one", "two"}


async def test_catalog_is_published_before_new_refs_and_read_after_refs(mocker: MockerFixture) -> None:
    blob, redis = FakeBlobStorageClient(), FakeRedisClient()
    storage = GitStore(blob, redis)
    await storage.load(PATH)
    for name in ("one", "two"):
        blob.put(f"{PATH}/packs/{name}.pack", PACK.pack)
        blob.put(f"{PATH}/packs/{name}.idx", PACK.index)
    ref_key = f"{PATH}/refs/refs/heads/main"
    original_set = redis.set

    async def set_ref(key: str, value: str | bytes) -> None:
        if key == ref_key:
            assert json.loads(redis.values[f"{PATH}/{CATALOG}"]) == ["one"]
            assert len(blob.objects) == 4
        await original_set(key, value)

    mocker.patch.object(redis, "set", side_effect=set_ref)
    await storage.save(PATH, {"pack_additions": {"one"}, "ref_puts": {b"refs/heads/main": b"1" * 40}})
    get = mocker.spy(redis, "get")
    await storage.load(PATH)
    assert [call.args[0] for call in get.await_args_list][:2] == [ref_key, f"{PATH}/{CATALOG}"]


async def test_pack_deletion_and_catalog_recovery(mocker: MockerFixture) -> None:
    blob, redis = FakeBlobStorageClient(), FakeRedisClient()
    storage = GitStore(blob, redis)
    await storage.load(PATH)
    for name in ("one", "two"):
        blob.put(f"{PATH}/packs/{name}.pack", PACK.pack)
        blob.put(f"{PATH}/packs/{name}.idx", PACK.index)
    await storage.save(PATH, {"pack_additions": {"one", "two"}})
    await storage.save(PATH, {"pack_deletes": {"one"}})
    assert set((await storage.load(PATH))[0]) == {"two"}
    await redis.delete(f"{PATH}/{CATALOG}")
    listing = mocker.spy(blob, "list_keys")
    assert set((await storage.load(PATH))[0]) == {"two"}
    assert listing.call_count == 1


async def test_copy_uses_catalog_and_delete_cleans_orphans_without_touching_neighbors(mocker: MockerFixture) -> None:
    blob, redis = FakeBlobStorageClient(), FakeRedisClient()
    storage = GitStore(blob, redis)
    await storage.load(PATH)
    for name in ("one", "two"):
        blob.put(f"{PATH}/packs/{name}.pack", PACK.pack)
        blob.put(f"{PATH}/packs/{name}.idx", PACK.index)
    await storage.save(PATH, {"pack_additions": {"one"}, "ref_puts": {b"HEAD": b"ref: refs/heads/main"}})
    target = "other/fork.git"
    await storage.load(target)
    listing = mocker.spy(blob, "list_keys")
    await storage.copy(PATH, target)
    assert await storage.load(PATH) == await storage.load(target)
    listing.assert_not_called()
    blob.put(f"{PATH}/packs/orphan.pack", b"partial")
    await storage.delete(PATH)
    assert not any(key.startswith(f"{PATH}/") for key in blob.objects)
    assert not any(key.startswith(f"{PATH}/") for key in redis.values)
    assert (await storage.load(target))[0] == {"one"}


async def test_missing_cataloged_index_fails_when_objects_are_accessed() -> None:
    blob, redis = FakeBlobStorageClient(), FakeRedisClient()
    storage = GitStore(blob, redis)
    await storage.save(PATH, {"pack_additions": {"one"}})
    names, _ = await storage.load(PATH)
    objects = BlobObjectStore(blob, f"{PATH}/packs/", names)
    with pytest.raises(FileNotFoundError):
        objects[Blob.from_string(b"missing").id]
