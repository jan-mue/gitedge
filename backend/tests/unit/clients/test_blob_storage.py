"""Vercel Blob pagination and immutable object caching."""

from types import SimpleNamespace
from typing import TYPE_CHECKING

from app.clients.blob_storage import VercelBlobClient

if TYPE_CHECKING:
    from pytest_mock import MockerFixture


async def test_vercel_lists_all_pages_with_maximum_page_size(mocker: MockerFixture) -> None:
    sdk = mocker.patch("app.clients.blob_storage.AsyncBlobClient").return_value
    sdk.list_objects = mocker.AsyncMock(
        side_effect=[
            SimpleNamespace(blobs=[SimpleNamespace(pathname="repo/one.pack")], has_more=True, cursor="next"),
            SimpleNamespace(blobs=[SimpleNamespace(pathname="repo/one.idx")], has_more=False, cursor=None),
        ]
    )
    client = VercelBlobClient()
    assert await client.list_keys("repo/") == ["repo/one.pack", "repo/one.idx"]
    assert sdk.list_objects.await_args_list == [
        mocker.call(prefix="repo/", cursor=None, limit=1000),
        mocker.call(prefix="repo/", cursor="next", limit=1000),
    ]


async def test_vercel_pack_uploads_use_long_cache_lifetime_and_cached_reads(mocker: MockerFixture) -> None:
    sdk = mocker.patch("app.clients.blob_storage.AsyncBlobClient").return_value
    sdk.put = mocker.AsyncMock()
    sdk.get = mocker.AsyncMock(return_value=SimpleNamespace(content=b"pack"))
    client = VercelBlobClient(access="private")
    await client.put("repo/packs/hash.pack", b"pack")
    assert sdk.put.await_args.kwargs["cache_control_max_age"] == 31536000
    assert sdk.put.await_args.kwargs["access"] == "private"
    assert sdk.put.await_args.kwargs["add_random_suffix"] is False
    assert await client.get("repo/packs/hash.pack") == b"pack"
    sdk.get.assert_awaited_once_with("repo/packs/hash.pack", access="private", use_cache=True)


async def test_mutable_vercel_blobs_overwrite_and_bypass_stale_cached_reads(mocker: MockerFixture) -> None:
    current: dict[str, bytes] = {}
    cached: dict[str, bytes] = {}

    async def put(key: str, data: bytes, *, overwrite: bool = False, **_: object) -> None:
        if key in current and not overwrite:
            raise RuntimeError("Blob already exists")
        current[key] = data

    async def get(key: str, *, use_cache: bool = True, **_: object) -> SimpleNamespace:
        cached.setdefault(key, current[key])
        return SimpleNamespace(content=cached[key] if use_cache else current[key])

    sdk = mocker.patch("app.clients.blob_storage.AsyncBlobClient").return_value
    sdk.put = mocker.AsyncMock(side_effect=put)
    sdk.get = mocker.AsyncMock(side_effect=get)
    client = VercelBlobClient(token="test")
    await client.put("actions/repository/cache.tar.gz", b"first job")
    assert await client.get("actions/repository/cache.tar.gz") == b"first job"
    await client.put("actions/repository/cache.tar.gz", b"second job")
    assert await client.get_current("actions/repository/cache.tar.gz") == b"second job"
