"""Redis client for Git ref storage."""

import json
from abc import ABC, abstractmethod

import redis.asyncio as aioredis
from upstash_redis.asyncio import Redis

from app.config import settings

_PUBLISH_MERGE = """
if redis.call('EXISTS', KEYS[6]) == 1 then return 0 end
if redis.call('GET', KEYS[1]) ~= ARGV[1] or redis.call('GET', KEYS[2]) ~= ARGV[2] then return 0 end
redis.call('SET', KEYS[1], ARGV[3])
redis.call('SET', KEYS[3], ARGV[1])
redis.call('SET', KEYS[4], ARGV[2])
redis.call('SET', KEYS[5], ARGV[3])
redis.call('SET', KEYS[6], ARGV[5])
if ARGV[4] == '1' then redis.call('DEL', KEYS[2]) end
return 1
"""


class AbstractRedisClient(ABC):
    """Abstract base class for Redis operations."""

    @abstractmethod
    async def publish_merge(self, keys: list[str], base: str, head: str, commit: str, delete_branch: bool) -> bool:
        """Atomically verify both branch tips, archive PR revisions and advance the base."""

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

    async def publish_merge(self, keys: list[str], base: str, head: str, commit: str, delete_branch: bool) -> bool:
        """Publish a merge with a single Redis compare-and-swap script."""
        return bool(
            await self._client.eval(
                _PUBLISH_MERGE,
                len(keys),
                *keys,
                base,
                head,
                commit,
                "1" if delete_branch else "0",
                json.dumps({"base": base, "head": head, "commit": commit}),
            )
        )

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

    async def publish_merge(self, keys: list[str], base: str, head: str, commit: str, delete_branch: bool) -> bool:
        """Publish a merge with a single Redis compare-and-swap script."""
        return bool(
            await self._client.eval(
                _PUBLISH_MERGE,
                keys=keys,
                args=[
                    base,
                    head,
                    commit,
                    "1" if delete_branch else "0",
                    json.dumps({"base": base, "head": head, "commit": commit}),
                ],
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
