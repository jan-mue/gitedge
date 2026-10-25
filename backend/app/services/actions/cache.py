"""Repository-scoped cache archives in Blob/S3 with searchable SQL metadata."""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from app.entities.actions import WorkflowCacheEntry
from app.schemas.actions import CacheEntry

if TYPE_CHECKING:
    from app.clients.actions_cache import ActionsCacheStore
    from app.clients.blob_storage import BlobStorageClient
    from app.schemas.actions import CacheIdentity

STATE_LIMIT = 32 * 1024 * 1024
CACHE_TTL = 7 * 24 * 60 * 60


class ActionsCacheService:
    """Upload complete archives before publishing their immutable identities."""

    def __init__(self, store: ActionsCacheStore, blobs: BlobStorageClient) -> None:
        """Reuse the application's object storage provider."""
        self.store = store
        self.blobs = blobs

    @staticmethod
    def _metadata(entry: WorkflowCacheEntry) -> CacheEntry:
        return CacheEntry(id=entry.payload_id, key=entry.key, version=entry.version, size=entry.size)

    @staticmethod
    def _key(entry: WorkflowCacheEntry) -> str:
        return f"actions/{entry.repo_id}/cache/{entry.payload_id}.bin"

    async def _read(self, entry: WorkflowCacheEntry) -> bytes | None:
        if entry.expires_at <= datetime.now(UTC):
            await self.blobs.delete(self._key(entry))
            return None
        if not 0 <= entry.size <= STATE_LIMIT:
            return None
        payload = await self.blobs.get_current(self._key(entry))
        if payload is None or len(payload) != entry.size or hashlib.sha256(payload).hexdigest() != entry.checksum:
            return None
        return payload

    async def lookup(self, repo_id: uuid.UUID, identity: CacheIdentity, restore_keys: list[str]) -> CacheEntry | None:
        """Prefer exact keys, then the newest valid match for each ordered prefix."""
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
        """Publish one complete generation and remove replaced or losing uploads."""
        if len(payload) > STATE_LIMIT:
            raise ValueError("Cache exceeds the 32 MiB transfer limit")
        candidates = await self.store.candidates(repo_id, identity.key, identity.version)
        existing = next((entry for entry in candidates if entry.key == identity.key), None)
        if existing and await self._read(existing) is not None:
            return self._metadata(existing)
        previous_id = existing.payload_id if existing else None
        previous_key = self._key(existing) if existing else None
        entry = WorkflowCacheEntry(
            repo_id=repo_id,
            key=identity.key,
            version=identity.version,
            payload_id=uuid.uuid4(),
            size=len(payload),
            checksum=hashlib.sha256(payload).hexdigest(),
            expires_at=datetime.now(UTC) + timedelta(seconds=CACHE_TTL),
        )
        await self.blobs.put(self._key(entry), payload)
        published = await self.store.publish(entry, previous_id)
        if published.payload_id != entry.payload_id:
            await self.blobs.delete(self._key(entry))
        elif previous_key:
            await self.blobs.delete(previous_key)
        return self._metadata(published)

    async def download(self, repo_id: uuid.UUID, payload_id: uuid.UUID) -> bytes | None:
        """Validate repository ownership, expiry, size, and archive integrity."""
        entry = await self.store.payload(repo_id, payload_id)
        return await self._read(entry) if entry else None
