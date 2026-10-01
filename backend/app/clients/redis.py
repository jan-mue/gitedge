"""Redis client for Git ref storage."""

from abc import ABC, abstractmethod

import redis.asyncio as aioredis
from upstash_redis.asyncio import Redis

from app.config import settings


class AbstractRedisClient(ABC):
    """Abstract base class for Redis operations."""

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
