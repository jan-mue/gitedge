"""Lazy pack access and transfer budgets across requests."""

from threading import get_ident
from typing import TYPE_CHECKING

import pytest
from dulwich.objects import Blob
from dulwich.refs import Ref
from fastapi.concurrency import run_in_threadpool

from app.clients.git import GitStore
from app.services.git.repository import MAX_CACHED_BYTES, BlobRepository
from tests.unit.utils.fakes import FakeBlobStorageClient, FakeCacheClient, FakeRedisClient

if TYPE_CHECKING:
    from os import PathLike

    from pytest_mock import MockerFixture


async def test_metadata_loading_does_not_download_objects(mocker: MockerFixture) -> None:
    blob, redis = FakeBlobStorageClient(), FakeRedisClient()
    prefix = "owner/repo.git/packs/"
    for index in range(10):
        blob.put(f"{prefix}pack-{index}.pack", b"pack")
        blob.put(f"{prefix}pack-{index}.idx", b"index")
    blob.put(f"{prefix}orphan.pack", b"orphan")
    download = mocker.spy(blob, "download")
    listing = mocker.spy(blob, "list_keys")
    store = GitStore(blob, redis)
    names, refs = await store.load("owner/repo.git")
    repo = BlobRepository(blob, prefix, names)
    repo.load_from_storage(refs)
    repo.refs.set_symbolic_ref(Ref(b"HEAD"), Ref(b"refs/heads/main"))
    await store.save("owner/repo.git", repo.get_pending_changes())
    await store.load("owner/repo.git")
    assert len(names) == 10
    download.assert_not_called()
    listing.assert_called_once()
    repo.close()


async def test_only_needed_pack_downloads_and_other_instances_reuse_shared_cache(mocker: MockerFixture) -> None:
    blob = FakeBlobStorageClient()
    prefix = "owner/repo.git/packs/"
    repo = BlobRepository.create(blob, prefix)
    wanted, unrelated = Blob.from_string(b"wanted"), Blob.from_string(b"unrelated")
    repo.object_store.add_objects([(wanted, None)])
    repo.object_store.add_objects([(unrelated, None)])
    names = set(repo.object_store.names)
    assert len(names) == 2
    repo.close()
    main_thread = get_ident()
    original = blob.download

    def download_in_worker(key: str, path: str | PathLike[str]) -> None:
        assert get_ident() != main_thread
        original(key, path)

    download = mocker.patch.object(blob, "download", side_effect=download_in_worker)
    uploads = mocker.spy(blob, "put")
    cache = FakeCacheClient()
    repo = BlobRepository(blob, prefix, names, cache=cache)
    assert await run_in_threadpool(repo.object_store.__getitem__, wanted.id) == wanted
    repo.close()
    keys = [call.args[0] for call in download.call_args_list]
    assert len([key for key in keys if key.endswith(".idx")]) == 2
    assert len([key for key in keys if key.endswith(".pack")]) == 1
    uploads.assert_not_called()

    other_blob = FakeBlobStorageClient()
    other_blob.objects.update(blob.objects)
    other_download = mocker.spy(other_blob, "download")
    repo = BlobRepository(other_blob, prefix, names, cache=cache)
    assert await run_in_threadpool(repo.object_store.__getitem__, wanted.id) == wanted
    repo.close()
    other_download.assert_not_called()

    repo = BlobRepository(other_blob, prefix, names, cache=cache)
    assert await run_in_threadpool(repo.object_store.__getitem__, unrelated.id) == unrelated
    repo.close()
    assert other_download.call_count == 1
    assert other_download.call_args.args[0].endswith(".pack")


async def test_new_pack_upload_does_not_read_existing_packs(mocker: MockerFixture) -> None:
    blob, cache = FakeBlobStorageClient(), FakeCacheClient()
    repo = BlobRepository.create(blob, "owner/repo.git/packs/")
    repo.object_store.add_objects([(Blob.from_string(b"old"), None)])
    names = set(repo.object_store.names)
    repo.close()
    download, put = mocker.spy(blob, "download"), mocker.spy(blob, "put")
    repo = BlobRepository(blob, "owner/repo.git/packs/", names, cache=cache)
    wanted = Blob.from_string(b"new")
    await run_in_threadpool(repo.object_store.add_objects, [(wanted, None)])
    assert put.call_count == 2
    assert all(name not in call.args[0] for call in download.call_args_list for name in names)
    await run_in_threadpool(repo.object_store.add_objects, [(wanted, None)])
    assert put.call_count == 2
    repo.close()


async def test_cached_objects_are_scoped_to_repository_and_survive_only_until_eviction(mocker: MockerFixture) -> None:
    blob, cache = FakeBlobStorageClient(), FakeCacheClient()
    wanted = Blob.from_string(b"private content")
    repo = BlobRepository.create(blob, "owner/private.git/packs/")
    repo.object_store.add_objects([(wanted, None)])
    names = set(repo.object_store.names)
    repo.close()
    repo = BlobRepository(blob, "owner/private.git/packs/", names, cache=cache)
    assert await run_in_threadpool(repo.object_store.__getitem__, wanted.id) == wanted
    repo.close()

    other = BlobRepository(blob, "owner/other.git/packs/", set(), cache=cache)
    with pytest.raises(KeyError):
        await run_in_threadpool(other.object_store.__getitem__, wanted.id)
    other.close()

    await cache.invalidate("git:owner/private.git")
    download = mocker.spy(blob, "download")
    repo = BlobRepository(blob, "owner/private.git/packs/", names, cache=cache)
    assert await run_in_threadpool(repo.object_store.__getitem__, wanted.id) == wanted
    assert download.call_count == 2
    repo.close()


async def test_large_objects_bypass_shared_cache_value_limits() -> None:
    blob, cache = FakeBlobStorageClient(), FakeCacheClient()
    wanted = Blob.from_string(b"a" * (MAX_CACHED_BYTES + 1))
    repo = BlobRepository.create(blob, "owner/repo.git/packs/", cache=cache)
    await run_in_threadpool(repo.object_store.add_objects, [(wanted, None)])
    assert await run_in_threadpool(repo.object_store.__getitem__, wanted.id) == wanted
    assert ("git:owner/repo.git", f"object:{wanted.id.decode()}") not in cache.values
    repo.close()
