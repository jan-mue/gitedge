"""Publish Git merge objects before atomically advancing refs."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import uuid

    from app.clients.blob_storage import BlobStorageClient
    from app.clients.cache import AbstractCacheClient
    from app.clients.git.blob_backend import BlobBackend
    from app.clients.git.types import MergeRequest, MergeResult
    from app.clients.redis import AbstractRedisClient
from dulwich.objects import ObjectID
from dulwich.refs import Ref
from fastapi import HTTPException, status
from fastapi.concurrency import run_in_threadpool

from app.clients.git.blob_repository import BlobRepository
from app.clients.git.merging import MergeConflict, calculate_merge, merge_message
from app.clients.git.refs import GitRefStore
from app.clients.git.storage import RepositoryStorage
from app.schemas.repositories import MergeMethod, PullRequestMergeability


class GitMergeClient:
    """Fresh Git reads and conditional merge publication shared across workers."""

    def __init__(
        self, blob: BlobStorageClient, redis: AbstractRedisClient, cache: AbstractCacheClient, backend: BlobBackend
    ) -> None:
        """Bind existing application storage clients."""
        self.blob, self.redis, self.cache, self.backend = blob, redis, cache, backend
        self.refs = GitRefStore(redis)
        self.storage = RepositoryStorage(blob, redis)

    async def load(self, owner: str, name: str) -> BlobRepository:
        """Load current refs instead of using a worker's potentially stale repository."""
        packs, refs = await self.storage.load(f"{owner}/{name}.git")
        repo = BlobRepository()
        repo.load_from_storage(packs, refs)
        return repo

    async def completed(self, owner: str, name: str, pull_id: uuid.UUID) -> MergeResult | None:
        """Recover publication if a response or database write was interrupted."""
        return await self.refs.completed_merge(owner, name, pull_id)

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
        changes["ref_puts"], changes["ref_deletes"] = {}, set()
        await self.storage.save(key, changes)
        published = await self.refs.publish_merge(
            owner,
            name,
            number,
            base_branch,
            head_branch,
            result,
            delete_branch,
            pull_id=pull_id,
        )
        if published:
            self.backend.remove_repository(key)
            await self.cache.invalidate(f"repo:{owner}/{name}")
        return published

    async def merge(self, request: MergeRequest) -> MergeResult:
        """Calculate objects and publish while both branch tips still match."""
        owner, name, number = request.owner, request.name, request.number
        repo = await self.load(owner, name)
        try:
            base_ref, head_ref = (
                Ref(f"refs/heads/{request.base_branch}".encode()),
                Ref(f"refs/heads/{request.head_branch}".encode()),
            )
            base, head = repo.refs.read_loose_ref(base_ref), repo.refs.read_loose_ref(head_ref)
            if base is None or head is None:
                raise HTTPException(status_code=409, detail="The base or PR branch no longer exists")
            if request.expected_head and head.decode() != request.expected_head:
                raise HTTPException(status_code=409, detail="The PR branch changed. Reload before merging.")
            if request.expected_base and base.decode() != request.expected_base:
                raise HTTPException(status_code=409, detail="The base branch changed. Reload before merging.")
            commits = await run_in_threadpool(
                lambda: [
                    entry.commit
                    for entry in repo.get_walker(
                        include=[ObjectID(head)], exclude=[ObjectID(base)], order="topo", reverse=True
                    )
                ]
            )
            if not commits:
                raise HTTPException(status_code=409, detail="The PR has no commits to merge")
            message = merge_message(
                request.template, request.title, request.body, request.head_branch, request.base_branch, commits
            )
            identity = request.identity
            result = await run_in_threadpool(
                calculate_merge, repo, ObjectID(base), ObjectID(head), request.method, message, identity
            )
            delete_branch = request.delete_branch
            if not await self.publish(
                owner,
                name,
                number,
                repo,
                request.base_branch,
                request.head_branch,
                result,
                delete_branch,
                pull_id=request.pull_id,
            ):
                raise HTTPException(status_code=409, detail="A branch changed during merging. Reload and try again.")
        finally:
            repo.object_store.close()
        return result
