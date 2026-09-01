"""Redis client for Git ref storage."""

import logging
from abc import ABC, abstractmethod

import redis.asyncio as aioredis
from upstash_redis.asyncio import Redis

from app.config import settings

logger = logging.getLogger(__name__)


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
        # Fallback for unexpected types
        return str(result).encode()

    async def set(self, key: str, value: str | bytes) -> None:
        """Set a value in Redis."""
        # upstash-redis takes str/bytes gracefully
        if isinstance(value, bytes):
            # Upstash REST API might prefer strings or might natively support binary if encoded.
            # Usually decode strings for Upstash caching unless binary explicitly desired.
            value = value.decode("utf-8", errors="ignore")
        await self._client.set(key, value)

    async def delete(self, key: str) -> None:
        """Delete a key from Redis."""
        await self._client.delete(key)

    async def scan_keys(self, pattern: str) -> list[str]:
        """Scan for keys matching a pattern."""
        # upstash-redis has scan
        cursor = 0
        keys: list[str] = []
        while True:
            cursor, partial_keys = await self._client.scan(cursor, match=pattern)
            keys.extend(partial_keys)
            if cursor == 0:
                break
        return keys


# Global mockable client instance (lazy initialized)
_redis_client: AbstractRedisClient | None = None


def get_redis_client() -> AbstractRedisClient:
    """Get or create the active Redis client.

    Returns:
        Redis client instance (Standard or Upstash).
    """
    global _redis_client  # noqa: PLW0603
    if _redis_client is None:
        _redis_client = UpstashRedisClient() if settings.REDIS_KIND == "rest" else RedisClient()
    return _redis_client


async def redis_get(key: str) -> bytes | None:
    """Get a value from Redis.

    Args:
        key: The Redis key.

    Returns:
        The value as bytes, or None if not found.
    """
    return await get_redis_client().get(key)


async def redis_set(key: str, value: str | bytes) -> None:
    """Set a value in Redis.

    Args:
        key: The Redis key.
        value: The value to store.
    """
    await get_redis_client().set(key, value)


async def redis_delete(key: str) -> None:
    """Delete a key from Redis.

    Args:
        key: The Redis key to delete.
    """
    await get_redis_client().delete(key)


async def redis_scan_keys(pattern: str) -> list[str]:
    """Scan for keys matching a pattern.

    Args:
        pattern: The key pattern to match (supports glob-style).

    Returns:
        List of matching keys as strings.
    """
    return await get_redis_client().scan_keys(pattern)
