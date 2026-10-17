"""Publish Git merge objects before atomically advancing refs."""

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import uuid

    from app.clients.blob_storage import BlobStorageClient
    from app.clients.cache import AbstractCacheClient
    from app.clients.redis import AbstractRedisClient
from app.services.blob_backend import BlobBackend, load_repository_from_storage, save_repository_changes_to_storage
from app.services.blob_repository import BlobRepository
from app.services.merging import MergeResult


class GitMergeClient:
    """Fresh Git reads and conditional merge publication shared across workers."""

    def __init__(
        self, blob: BlobStorageClient, redis: AbstractRedisClient, cache: AbstractCacheClient, backend: BlobBackend
    ) -> None:
        """Bind existing application storage clients."""
        self.blob, self.redis, self.cache, self.backend = blob, redis, cache, backend

    async def load(self, owner: str, name: str) -> BlobRepository:
        """Load current refs instead of using a worker's potentially stale repository."""
        packs, refs = await load_repository_from_storage(self.blob, self.redis, f"{owner}/{name}.git")
        repo = BlobRepository()
        repo.load_from_storage(packs, refs)
        return repo

    async def completed(self, owner: str, name: str, pull_id: uuid.UUID) -> MergeResult | None:
        """Recover publication if a response or database write was interrupted."""
        checkpoint = await self.redis.get(f"{owner}/{name}.git/merge-state/{pull_id}")
        return MergeResult(**json.loads(checkpoint)) if checkpoint else None

    async def publish(
        self,
        owner: str,
        name: str,
        number: int,
        repo: BlobRepository,
        base_branch: str,
        head_branch: str,
        result: MergeResult,
        delete_branch: bool,
        *,
        pull_id: uuid.UUID,
    ) -> bool:
        """Durably upload objects, then verify both tips and publish all refs atomically."""
        key = f"{owner}/{name}.git"
        changes = repo.get_pending_changes()
        # No branch is visible until all objects are durable.
        changes["ref_puts"], changes["ref_deletes"] = {}, set()
        await save_repository_changes_to_storage(self.blob, self.redis, key, changes)
        prefix = f"{key}/refs/refs/"
        published = await self.redis.publish_merge(
            [
                prefix + "heads/" + base_branch,
                prefix + "heads/" + head_branch,
                prefix + f"pull/{number}/base",
                prefix + f"pull/{number}/head",
                prefix + f"pull/{number}/merge",
                f"{key}/merge-state/{pull_id}",
            ],
            result.base,
            result.head,
            result.commit,
            delete_branch,
        )
        if published:
            self.backend.remove_repository(key)
            await self.cache.invalidate(f"repo:{owner}/{name}")
        return published
