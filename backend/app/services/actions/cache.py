"""Bounded repository caches backed by Vercel Runtime Cache or local Redis."""

from __future__ import annotations

import asyncio
import base64
import binascii
import hashlib
import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from app.entities.actions import WorkflowCacheEntry
from app.schemas.actions_cache import CacheEntry

if TYPE_CHECKING:
    from app.clients.actions_cache import ActionsCacheStore
    from app.clients.cache import AbstractCacheClient
    from app.schemas.actions_cache import CacheIdentity

STATE_LIMIT = 32 * 1024 * 1024
CHUNK_SIZE = 256 * 1024
CACHE_TTL = 7 * 24 * 60 * 60


class ActionsCacheService:
    """Publish chunks before metadata; eviction/corruption is a cache miss."""

    def __init__(self, store: ActionsCacheStore, cache: AbstractCacheClient) -> None:
        """Reuse the application's provider-selected cache client."""
        self.store = store
        self.cache = cache

    @staticmethod
    def _metadata(entry: WorkflowCacheEntry) -> CacheEntry:
        return CacheEntry(id=entry.payload_id, key=entry.key, version=entry.version, size=entry.size)

    @staticmethod
    def _group(repo_id: uuid.UUID) -> str:
        return f"actions:{repo_id}"

    async def _read(self, entry: WorkflowCacheEntry) -> bytes | None:
        if entry.expires_at <= datetime.now(UTC) or not 0 <= entry.size <= STATE_LIMIT:
            return None
        count = (entry.size + CHUNK_SIZE - 1) // CHUNK_SIZE
        chunks = []
        for start in range(0, count, 8):
            batch = await asyncio.gather(
                *(
                    self.cache.get(f"{entry.payload_id}:{index}", group=self._group(entry.repo_id))
                    for index in range(start, min(start + 8, count))
                )
            )
            for chunk in batch:
                if chunk is None or len(chunk) > 4 * ((CHUNK_SIZE + 2) // 3):
                    return None
                try:
                    chunks.append(base64.b64decode(chunk, validate=True))
                except binascii.Error, ValueError:
                    return None
        payload = b"".join(chunks)
        if len(payload) != entry.size or hashlib.sha256(payload).hexdigest() != entry.checksum:
            return None
        return payload

    async def lookup(self, repo_id: uuid.UUID, identity: CacheIdentity, restore_keys: list[str]) -> CacheEntry | None:
        """Prefer exact keys, then the newest viable match for each ordered prefix."""
        seen: set[uuid.UUID] = set()
        for prefix in [identity.key, *restore_keys]:
            candidates = await self.store.candidates(repo_id, prefix, identity.version)
            if prefix == identity.key:
                candidates.sort(key=lambda entry: entry.key != identity.key)
            for entry in candidates:
                if entry.payload_id in seen:
                    continue
                seen.add(entry.payload_id)
                if await self._read(entry) is not None:
                    return self._metadata(entry)
        return None

    async def save(self, repo_id: uuid.UUID, identity: CacheIdentity, payload: bytes) -> CacheEntry:
        """Write independent generations so parallel jobs preserve unrelated keys."""
        if len(payload) > STATE_LIMIT:
            raise ValueError("Cache exceeds the 32 MiB transfer limit")
        candidates = await self.store.candidates(repo_id, identity.key, identity.version)
        existing = next((entry for entry in candidates if entry.key == identity.key), None)
        if existing and await self._read(existing) is not None:
            return self._metadata(existing)
        entry = WorkflowCacheEntry(
            repo_id=repo_id,
            key=identity.key,
            version=identity.version,
            payload_id=uuid.uuid4(),
            size=len(payload),
            checksum=hashlib.sha256(payload).hexdigest(),
            expires_at=datetime.now(UTC) + timedelta(seconds=CACHE_TTL),
        )
        chunks = [payload[offset : offset + CHUNK_SIZE] for offset in range(0, len(payload), CHUNK_SIZE)]
        for start in range(0, len(chunks), 8):
            await asyncio.gather(
                *(
                    self.cache.set(
                        f"{entry.payload_id}:{index}",
                        base64.b64encode(chunks[index]).decode(),
                        ttl=CACHE_TTL,
                        group=self._group(repo_id),
                    )
                    for index in range(start, min(start + 8, len(chunks)))
                )
            )
        return self._metadata(await self.store.publish(entry, existing.payload_id if existing else None))

    async def download(self, repo_id: uuid.UUID, payload_id: uuid.UUID) -> bytes | None:
        """Revalidate chunks after lookup; eviction remains an ordinary miss."""
        entry = await self.store.payload(repo_id, payload_id)
        return await self._read(entry) if entry else None

    async def delete_repository(self, repo_id: uuid.UUID) -> None:
        """Invalidate chunks after repository deletion; metadata cascades in SQL."""
        await self.cache.invalidate(self._group(repo_id))
