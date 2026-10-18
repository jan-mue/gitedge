"""Repository pack downloads overlap while keeping network concurrency bounded."""

import asyncio
from typing import TYPE_CHECKING

from app.clients.git import GitStore
from tests.unit.utils.fakes import FakeBlobStorageClient, FakeRedisClient

if TYPE_CHECKING:
    from pytest_mock import MockerFixture


async def test_pack_downloads_overlap_without_unbounded_fanout(mocker: MockerFixture) -> None:
    blob = FakeBlobStorageClient()
    redis = FakeRedisClient()
    prefix = "owner/repo.git/packs/"
    for index in range(10):
        await blob.put(f"{prefix}pack-{index}.pack", b"pack")
        await blob.put(f"{prefix}pack-{index}.idx", b"index")
    await blob.put(f"{prefix}orphan.pack", b"orphan")
    active = peak = 0

    async def read(key: str) -> bytes | None:
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        await asyncio.sleep(0)
        active -= 1
        return blob.objects.get(key)

    mocker.patch.object(blob, "get", side_effect=read)
    packs, _ = await GitStore(blob, redis).load("owner/repo.git")
    assert len(packs) == 10
    assert 2 <= peak <= 8
    assert all(pack.pack == b"pack" and pack.index == b"index" for pack in packs.values())
