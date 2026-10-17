"""Redis client for Git ref storage."""

import json
import logging
from abc import ABC, abstractmethod

import redis.asyncio as aioredis
from redis.exceptions import WatchError
from upstash_redis.asyncio import Redis

from app.config import settings

logger = logging.getLogger(__name__)

_COMPARE_AND_SET = """
local expected = cjson.decode(ARGV[1])
local updates = cjson.decode(ARGV[2])
for _, key in ipairs(KEYS) do
    local value = expected[key]
    if value == cjson.null then
        if redis.call('EXISTS', key) == 1 then return 0 end
    elseif value ~= nil and redis.call('GET', key) ~= value then
        return 0
    end
end
for _, key in ipairs(KEYS) do
    local value = updates[key]
    if value == cjson.null then
        redis.call('DEL', key)
    elseif value ~= nil then
        redis.call('SET', key, value)
    end
end
return 1
"""


class AbstractRedisClient(ABC):
    """Abstract base class for Redis operations."""

    @abstractmethod
    async def compare_and_set(self, expected: dict[str, str | None], updates: dict[str, str | None]) -> bool:
        """Apply updates only if every expected value matches; None means absent or delete."""

    @abstractmethod
    async def get(self, key: str) -> bytes | None:
        """Get a value from Redis."""

    @abstractmethod
    async def set(self, key: str, value: str | bytes) -> None:
        """Set a value in Redis."""

    @abstractmethod
    async def delete(self, key: str) -> None:
        """Delete a key from Redis."""

    @abstractmethod
    async def scan_keys(self, pattern: str) -> list[str]:
        """Scan for keys matching a pattern."""


class RedisClient(AbstractRedisClient):
    """Standard Redis client using redis-py."""

    def __init__(self) -> None:
        """Initialize the standard Redis client."""
        self._client = aioredis.from_url(settings.REDIS_URL, password=settings.REDIS_PASSWORD, decode_responses=False)

    async def compare_and_set(self, expected: dict[str, str | None], updates: dict[str, str | None]) -> bool:
        """Use the SDK's optimistic transaction to check and update keys atomically."""
        async with self._client.pipeline() as transaction:
            try:
                if expected:
                    await transaction.watch(*expected)
                    current = await transaction.mget(list(expected))
                    if current != [value.encode() if value is not None else None for value in expected.values()]:
                        return False
                transaction.multi()
                for key, value in updates.items():
                    if value is None:
                        transaction.delete(key)
                    else:
                        transaction.set(key, value)
                await transaction.execute()
            except WatchError as error:
                logger.debug("Redis transaction conflicted: %s", error)
                return False
        return True

    async def get(self, key: str) -> bytes | None:
        """Get a value from Redis."""
        result = await self._client.get(key)
        if result is None:
            return None
        if isinstance(result, str):
            return result.encode()
        return bytes(result)

    async def set(self, key: str, value: str | bytes) -> None:
        """Set a value in Redis."""
        await self._client.set(key, value)

    async def delete(self, key: str) -> None:
        """Delete a key from Redis."""
        await self._client.delete(key)

    async def scan_keys(self, pattern: str) -> list[str]:
        """Scan for keys matching a pattern."""
        keys: list[str] = []
        async for key in self._client.scan_iter(match=pattern):
            if isinstance(key, bytes):
                keys.append(key.decode())
            else:
                keys.append(str(key))
        return keys


class UpstashRedisClient(AbstractRedisClient):
    """Redis client for Upstash Serverless using upstash-redis."""

    def __init__(self) -> None:
        """Initialize the Upstash Redis client."""
        self._client = Redis(url=settings.REDIS_URL or "", token=settings.REDIS_PASSWORD or "")

    async def compare_and_set(self, expected: dict[str, str | None], updates: dict[str, str | None]) -> bool:
        """Use a server-side condition because REST transactions do not support WATCH."""
        return bool(
            await self._client.eval(
                _COMPARE_AND_SET,
                keys=list(dict.fromkeys([*expected, *updates])),
                args=[json.dumps(expected), json.dumps(updates)],
            )
        )

    async def get(self, key: str) -> bytes | None:
        """Get a value from Redis."""
        # upstash-redis returns parsed strings by default for standard values
        result = await self._client.get(key)
        if result is None:
            return None
        if isinstance(result, str):
            return result.encode()
        if isinstance(result, bytes):
            return result
        return str(result).encode()

    async def set(self, key: str, value: str | bytes) -> None:
        """Set a value in Redis."""
        if isinstance(value, bytes):
            value = value.decode("utf-8", errors="ignore")
        await self._client.set(key, value)

    async def delete(self, key: str) -> None:
        """Delete a key from Redis."""
        await self._client.delete(key)

    async def scan_keys(self, pattern: str) -> list[str]:
        """Scan for keys matching a pattern."""
        cursor = 0
        keys: list[str] = []
        while True:
            cursor, partial_keys = await self._client.scan(cursor, match=pattern)
            keys.extend(partial_keys)
            if cursor == 0:
                break
        return keys
