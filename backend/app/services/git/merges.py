"""Publish Git merge objects before atomically advancing refs."""

import json
from dataclasses import asdict
from time import time
from typing import TYPE_CHECKING

from dulwich.graph import find_merge_base
from dulwich.merge import recursive_merge, three_way_merge
from dulwich.object_store import MemoryObjectStore, OverlayObjectStore
from dulwich.objects import Commit, ObjectID
from fastapi import HTTPException

from app.types import MergeResult

if TYPE_CHECKING:
    import uuid

    from app.services.git.repositories import GitService
    from app.services.git.repository import BlobRepository
    from app.types import MergeRequest
from dulwich.refs import Ref
from fastapi import status
from fastapi.concurrency import run_in_threadpool

from app.schemas.repositories import MergeMessage, MergeMethod, PullRequestMergeability


class GitMergeService:
    """Fresh Git reads and conditional merge publication shared across workers."""

    def __init__(self, git: GitService) -> None:
        """Share storage and response caching with the request's Git service."""
        self.git = git
        self.storage = git.storage
        self.cache = git.cache_client

    async def completed(self, owner: str, name: str, pull_id: uuid.UUID) -> MergeResult | None:
        """Recover publication if a response or database write was interrupted."""
        return await self.storage.completed_merge(owner, name, pull_id)

    async def check(self, owner: str, name: str, base: str, head: str, method: MergeMethod) -> PullRequestMergeability:
        """Cache a read-only calculation by immutable tips and strategy, never by branch name."""
        group = f"repo:{owner}/{name}"
        key = f"mergeability:v1:{owner}/{name}:{base}:{head}:{method}"
        cached = await self.cache.get(key, group=group)
        if cached:
            return PullRequestMergeability.model_validate_json(cached)
        repo = await self.git.load_repository(owner, name, fresh=True)
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
        base = f"refs/refs/heads/{base_branch}"
        head = f"refs/refs/heads/{head_branch}"
        checkpoint = f"merge-state/{pull_id}"
        updates: dict[str, str | None] = {
            base: result.commit,
            f"refs/refs/pull/{number}/base": result.base,
            f"refs/refs/pull/{number}/head": result.head,
            f"refs/refs/pull/{number}/merge": result.commit,
            checkpoint: json.dumps(asdict(result)),
        }
        if delete_branch:
            updates[head] = None
        published = await self.storage.compare_and_set(
            key, {base: result.base, head: result.head, checkpoint: None}, updates
        )
        if published:
            if loaded := self.git.repositories.pop(key, None):
                loaded.close()
            await self.cache.invalidate(f"repo:{owner}/{name}")
        return published

    async def merge(self, request: MergeRequest) -> MergeResult:
        """Calculate objects and publish while both branch tips still match."""
        owner, name, number = request.owner, request.name, request.number
        repo = await self.git.load_repository(owner, name, fresh=True)
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


MAX_CONFLICT_PATHS = 10


class MergeConflict(HTTPException):
    """Expected conflict with structured paths for the read-only preflight."""

    def __init__(self, paths: list[str], detail: str) -> None:
        """Keep the normal merge error and the complete list of affected paths."""
        super().__init__(status_code=409, detail=detail)
        self.paths = paths


def reject_conflicts(conflicts: list[bytes], operation: str) -> None:
    """Explain expected Git conflicts without publishing any changes."""
    if not conflicts:
        return
    paths = [path.decode("utf-8", errors="replace") for path in conflicts]
    visible = ", ".join(paths[:MAX_CONFLICT_PATHS])
    remaining = f" and {len(paths) - MAX_CONFLICT_PATHS} more files" if len(paths) > MAX_CONFLICT_PATHS else ""
    raise MergeConflict(
        paths=paths,
        detail=f"{operation} has conflicts in {visible}{remaining}. Resolve them on the PR branch before merging.",
    )


def merge_message(
    template: MergeMessage, title: str, body: str | None, head: str, base: str, commits: list[Commit]
) -> bytes:
    """Expand a repository's message template using the original PR commits."""
    if template == MergeMessage.DEFAULT:
        message = f"Merge {head} into {base}"
    elif template == MergeMessage.TITLE_DESCRIPTION:
        message = title + (f"\n\n{body.strip()}" if body and body.strip() else "")
    elif template == MergeMessage.TITLE_COMMITS:
        details = "\n\n".join(commit.message.decode("utf-8", errors="replace").strip() for commit in commits)
        message = title + (f"\n\n{details}" if details else "")
    elif template == MergeMessage.TITLE:
        message = title
    return (message.rstrip() + "\n").encode()


def calculate_merge(
    repo: BlobRepository,
    base: ObjectID,
    head: ObjectID,
    method: MergeMethod,
    message: bytes,
    identity: bytes,
    *,
    write_objects: bool = True,
) -> MergeResult:
    """Calculate in memory, optionally staging objects for actual publication."""
    pending = MemoryObjectStore()
    store = OverlayObjectStore([pending, repo.object_store], add_store=pending)
    ours, theirs = store[base], store[head]
    if not isinstance(ours, Commit) or not isinstance(theirs, Commit):
        raise HTTPException(status_code=409, detail="Branch refs must point to commits")
    bases = find_merge_base(repo, [base, head])
    if not bases:
        raise HTTPException(status_code=409, detail="Branches have no common ancestor")
    if head in bases:
        raise HTTPException(status_code=409, detail="The PR has no commits to merge")

    def commit(tree: ObjectID, parents: list[ObjectID], body: bytes, original: Commit | None = None) -> Commit:
        result = Commit()
        result.tree, result.parents, result.message = tree, parents, body
        result.committer = identity
        result.author = original.author if original else identity
        result.commit_time = int(time())
        result.author_time = original.author_time if original else result.commit_time
        result.author_timezone = original.author_timezone if original else 0
        result.commit_timezone = 0
        store.add_object(result)
        return result

    if method == MergeMethod.REBASE:
        entries = [
            entry
            for entry in repo.get_walker(include=[head], exclude=[base], order="topo", reverse=True)
            if len(entry.commit.parents) <= 1
        ]
        current = ours
        for index, entry in enumerate(entries):
            original = entry.commit
            ancestor = store[original.parents[0]] if original.parents else None
            if ancestor is not None and not isinstance(ancestor, Commit):
                raise HTTPException(status_code=409, detail="PR history contains an invalid parent")
            tree, conflicts = three_way_merge(store, ancestor, current, original)
            reject_conflicts(conflicts, "Rebase")
            store.add_object(tree)
            current = commit(
                tree.id, [current.id], message if index == len(entries) - 1 else original.message, original
            )
        if not entries:
            raise HTTPException(status_code=409, detail="The PR has no commits to rebase")
        result = current
    else:
        tree, conflicts = recursive_merge(store, bases, ours, theirs)
        reject_conflicts(conflicts, "Merge")
        store.add_object(tree)
        result = commit(tree.id, [base, head] if method == MergeMethod.MERGE else [base], message)
    if write_objects:
        repo.object_store.add_objects([(pending[sha], None) for sha in pending])
    return MergeResult(base.decode(), head.decode(), result.id.decode())
