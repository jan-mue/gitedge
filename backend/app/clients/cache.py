"""Cache client for derived repository responses.

Git content is mostly static or immutable, so responses such as tree listings,
highlighted files and commit details are cached in a shared cache instead of
recomputing them (and reloading repository data) on every request. Entries are
grouped by repository so a push can invalidate a whole repository at once.

Two backends are available: Redis (via fastapi-redis-sdk) for local development
and tests, and the Vercel Runtime Cache for deployed environments.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod

import redis.asyncio as aioredis
from redis_fastapi import CacheBackend
from vercel.cache import RuntimeCacheError
from vercel.functions import AsyncRuntimeCache

from app.config import settings

logger = logging.getLogger(__name__)


class AbstractCacheClient(ABC):
    """Async cache with group-based invalidation."""

    @abstractmethod
    async def get(self, key: str, *, group: str) -> str | None:
        """Return a cached value.

        Args:
            key: Cache key within the group.
            group: Group used for bulk invalidation (e.g. a repository).

        Returns:
            The cached value, or None on a miss.
        """

    @abstractmethod
    async def set(self, key: str, value: str, *, ttl: int, group: str) -> None:
        """Store a value.

        Args:
            key: Cache key within the group.
            value: String value to store.
            ttl: Time to live in seconds.
            group: Group used for bulk invalidation (e.g. a repository).
        """

    @abstractmethod
    async def invalidate(self, group: str) -> None:
        """Drop every entry in a group.

        Args:
            group: Group to invalidate.
        """


class NoopCacheClient(AbstractCacheClient):
    """Cache that never stores anything."""

    async def get(self, key: str, *, group: str) -> str | None:  # noqa: ARG002
        """Return None.

        Args:
            key: Cache key within the group.
            group: Group used for bulk invalidation.

        Returns:
            Always None.
        """
        return None

    async def set(self, key: str, value: str, *, ttl: int, group: str) -> None:
        """Do nothing.

        Args:
            key: Cache key within the group.
            value: String value to store.
            ttl: Time to live in seconds.
            group: Group used for bulk invalidation.
        """

    async def invalidate(self, group: str) -> None:
        """Do nothing.

        Args:
            group: Group to invalidate.
        """


class RedisCacheClient(AbstractCacheClient):
    """Redis-backed cache using fastapi-redis-sdk."""

    def __init__(self, url: str, password: str | None) -> None:
        """Initialize the Redis cache client.

        Args:
            url: Redis connection URL.
            password: Optional Redis password.
        """
        redis = aioredis.from_url(url, password=password, decode_responses=True)
        self._backend = CacheBackend(redis)

    async def get(self, key: str, *, group: str) -> str | None:
        """Return a cached value.

        Args:
            key: Cache key within the group.
            group: Group used for bulk invalidation.

        Returns:
            The cached value, or None on a miss or error.
        """
        value = await self._backend.get(key, eviction_group=group)
        return value if isinstance(value, str) else None

    async def set(self, key: str, value: str, *, ttl: int, group: str) -> None:
        """Store a value.

        Args:
            key: Cache key within the group.
            value: String value to store.
            ttl: Time to live in seconds.
            group: Group used for bulk invalidation.
        """
        await self._backend.set(key, value, ttl=ttl, eviction_group=group)

    async def invalidate(self, group: str) -> None:
        """Drop every entry in a group.

        Args:
            group: Group to invalidate.
        """
        await self._backend.delete_group(group)


class VercelCacheClient(AbstractCacheClient):
    """Cache backed by the Vercel Runtime Cache."""

    def __init__(self, namespace: str) -> None:
        """Initialize the Vercel cache client.

        Args:
            namespace: Namespace prefixed to every cache key.
        """
        self._cache = AsyncRuntimeCache(namespace=namespace)

    async def get(self, key: str, *, group: str) -> str | None:  # noqa: ARG002
        """Return a cached value.

        Args:
            key: Cache key within the group.
            group: Group used for bulk invalidation.

        Returns:
            The cached value, or None on a miss or error.
        """
        try:
            value = await self._cache.get(key)
        except (RuntimeCacheError, OSError) as e:
            logger.warning("Vercel cache get failed for %s: %s", key, e)
            return None
        return value if isinstance(value, str) else None

    async def set(self, key: str, value: str, *, ttl: int, group: str) -> None:
        """Store a value.

        Args:
            key: Cache key within the group.
            value: String value to store.
            ttl: Time to live in seconds.
            group: Group used for bulk invalidation (stored as a cache tag).
        """
        try:
            await self._cache.set(key, value, {"ttl": ttl, "tags": [group]})
        except (RuntimeCacheError, OSError) as e:
            logger.warning("Vercel cache set failed for %s: %s", key, e)

    async def invalidate(self, group: str) -> None:
        """Expire every entry tagged with a group.

        Args:
            group: Group to invalidate.
        """
        try:
            await self._cache.expire_tag(group)
        except (RuntimeCacheError, OSError) as e:
            logger.warning("Vercel cache invalidate failed for %s: %s", group, e)


def build_cache_client() -> AbstractCacheClient:
    """Build the cache client for the configured backend.

    ``CACHE_KIND="auto"`` uses the Vercel Runtime Cache when deployed and Redis
    otherwise.

    Returns:
        A cache client matching ``settings.CACHE_KIND``.
    """
    kind = settings.CACHE_KIND
    if kind == "auto":
        kind = "vercel" if settings.VERCEL_ENV != "development" else "redis"
    if kind == "vercel":
        return VercelCacheClient(settings.CACHE_NAMESPACE)
    if kind == "redis":
        return RedisCacheClient(settings.REDIS_URL, settings.REDIS_PASSWORD)
    return NoopCacheClient()
