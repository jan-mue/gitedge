"""Publish Git merge objects before atomically advancing refs."""

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import uuid

    from app.clients.blob_storage import BlobStorageClient
    from app.clients.cache import AbstractCacheClient
    from app.clients.redis import AbstractRedisClient
from dulwich.objects import ObjectID
from fastapi import HTTPException, status
from fastapi.concurrency import run_in_threadpool

from app.schemas.repositories import MergeMethod, PullRequestMergeability
from app.services.blob_backend import BlobBackend, load_repository_from_storage, save_repository_changes_to_storage
from app.services.blob_repository import BlobRepository
from app.services.merging import MergeConflict, MergeResult, calculate_merge


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

    async def check(self, owner: str, name: str, base: str, head: str, method: MergeMethod) -> PullRequestMergeability:
        """Cache a read-only calculation by immutable tips and strategy, never by branch name."""
        group = f"repo:{owner}/{name}"
        key = f"mergeability:v1:{owner}/{name}:{base}:{head}:{method}"
        cached = await self.cache.get(key, group=group)
        if cached:
            return PullRequestMergeability.model_validate_json(cached)
        repo = await self.load(owner, name)
        result = PullRequestMergeability(mergeable=True, base_commit=base, head_commit=head)
        try:
            await run_in_threadpool(
                calculate_merge,
                repo,
                ObjectID(base.encode()),
                ObjectID(head.encode()),
                method,
                b"Mergeability check\n",
                b"GitEdge <mergeability@gitedge.local>",
                write_objects=False,
            )
        except HTTPException as error:
            if error.status_code != status.HTTP_409_CONFLICT:
                raise
            result.mergeable, result.reason = False, str(error.detail)
            if isinstance(error, MergeConflict):
                result.conflicting_files = error.paths
        finally:
            repo.object_store.close()
        await self.cache.set(key, result.model_dump_json(), ttl=3600, group=group)
        return result

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
