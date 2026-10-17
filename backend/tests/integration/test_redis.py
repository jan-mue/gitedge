"""Verify both atomic-update adapters against a real Redis server."""

import asyncio
from typing import TYPE_CHECKING

import pytest
import redis.asyncio as aioredis

from app.clients.redis import RedisClient, UpstashRedisClient

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from pytest_mock import MockerFixture

    from app.clients.redis import AbstractRedisClient


@pytest.fixture(params=["redis", "upstash"])
async def adapter(
    request: pytest.FixtureRequest, infrastructure: dict[str, str], mocker: MockerFixture
) -> AsyncGenerator[AbstractRedisClient]:
    """Run the REST adapter's script on the same server used for SDK transactions."""
    client = aioredis.from_url(infrastructure["REDIS_URL"], decode_responses=False)
    if request.param == "redis":
        mocker.patch("app.clients.redis.aioredis.from_url", return_value=client)
        adapter = RedisClient()
    else:

        async def evaluate(script: str, keys: list[str], args: list[str]) -> object:
            return await client.eval(script, len(keys), *keys, *args)

        sdk = mocker.Mock(get=client.get, set=client.set, delete=client.delete, eval=evaluate)
        mocker.patch("app.clients.redis.Redis", return_value=sdk)
        adapter = UpstashRedisClient()
    await client.flushdb()
    yield adapter
    await client.aclose()


async def test_atomic_updates_reject_conflicts_and_checkpoint_reuse(adapter: AbstractRedisClient) -> None:
    """Failed conditions leave every key intact; successful updates include deletions."""
    await adapter.set("base", "base-sha")
    await adapter.set("head", "head-sha")
    expected = {"base": "base-sha", "head": "head-sha", "checkpoint": None}
    updates = {"base": "merged-sha", "head": None, "checkpoint": "saved-result"}
    assert not await adapter.compare_and_set({**expected, "head": "stale-sha"}, updates)
    assert await adapter.get("base") == b"base-sha"
    assert await adapter.get("head") == b"head-sha"
    assert await adapter.get("checkpoint") is None
    assert await adapter.compare_and_set(expected, updates)
    assert await adapter.get("base") == b"merged-sha"
    assert await adapter.get("head") is None
    assert await adapter.get("checkpoint") == b"saved-result"
    await adapter.set("base", "base-sha")
    await adapter.set("head", "head-sha")
    assert not await adapter.compare_and_set(expected, updates)
    assert await adapter.get("base") == b"base-sha"
    assert await adapter.get("head") == b"head-sha"


async def test_concurrent_atomic_updates_have_one_winner(adapter: AbstractRedisClient) -> None:
    """Competing publications cannot both advance the same revision."""
    await adapter.set("base", "original")
    results = await asyncio.gather(
        adapter.compare_and_set({"base": "original"}, {"base": "first"}),
        adapter.compare_and_set({"base": "original"}, {"base": "second"}),
    )
    assert sorted(results) == [False, True]
    assert await adapter.get("base") == (b"first" if results[0] else b"second")
