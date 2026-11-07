from __future__ import annotations

import base64
import json
from typing import TYPE_CHECKING

import pytest
from upstash_redis.asyncio import Redis

from app.clients.redis import UpstashRedisClient
from app.config import settings
from app.exceptions import RedisUnavailableError

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from pytest_mock import MockerFixture
    from respx import Router


@pytest.fixture
async def redis(mocker: MockerFixture) -> AsyncIterator[UpstashRedisClient]:
    mocker.patch.object(settings, "REDIS_URL", "https://redis.test")
    mocker.patch.object(settings, "REDIS_PASSWORD", "unit-token")
    async with Redis(url="https://redis.test", token="unit-token") as sdk:
        mocker.patch("app.clients.redis.Redis", return_value=sdk)
        yield UpstashRedisClient()


@pytest.mark.httpx2(using="httpcore")
async def test_recent_logs_use_the_sdk_and_decode_redis_streams(redis: UpstashRedisClient, httpx2_mock: Router) -> None:
    append = httpx2_mock.post("https://redis.test").respond(json={"result": 1})
    await redis.stream_add("logs:attempt", 2, '{"records":[]}')
    command = json.loads(append.calls.last.request.content)
    assert command[0] == "EVAL"
    assert command[-4:] == [1, "logs:attempt", "2-0", '{"records":[]}']
    encoded = [base64.b64encode(value.encode()).decode() for value in ["2-0", "data", '{"records":[]}']]
    httpx2_mock.post("https://redis.test").respond(json={"result": [[encoded[0], encoded[1:]]]})
    assert await redis.stream_read("logs:attempt", 1) == [b'{"records":[]}']


@pytest.mark.httpx2(using="httpcore")
async def test_redis_server_errors_become_a_specific_delivery_error(
    redis: UpstashRedisClient, httpx2_mock: Router
) -> None:
    httpx2_mock.post("https://redis.test").respond(json={"error": "ERR unavailable"})
    with pytest.raises(RedisUnavailableError, match="transport"):
        await redis.stream_add("logs:attempt", 2, "data")
    with pytest.raises(RedisUnavailableError, match="transport"):
        await redis.stream_read("logs:attempt", 1)


@pytest.mark.httpx2(using="httpcore")
@pytest.mark.parametrize("row", [[], ["Mi0w"], ["Mi0w", []], ["Mi0w", ["ZGF0YQ==", 123]]])
async def test_malformed_tail_entries_can_be_replayed_from_the_archive(
    redis: UpstashRedisClient, httpx2_mock: Router, row: list[object]
) -> None:
    httpx2_mock.post("https://redis.test").respond(json={"result": [row]})
    with pytest.raises(RedisUnavailableError, match="Malformed"):
        await redis.stream_read("logs:attempt", 1)
