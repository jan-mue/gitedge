"""Mutable workflow state must behave consistently across blob providers."""

from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING

from app.clients.blob_storage import VercelBlobClient

if TYPE_CHECKING:
    from pytest_mock import MockerFixture


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
