"""Git merge calculation without changing branch refs."""

from dataclasses import dataclass
from time import time
from typing import TYPE_CHECKING

from dulwich.graph import find_merge_base
from dulwich.merge import recursive_merge, three_way_merge
from dulwich.object_store import MemoryObjectStore, OverlayObjectStore
from dulwich.objects import Commit, ObjectID
from fastapi import HTTPException

from app.schemas.repositories import MergeMessage, MergeMethod

if TYPE_CHECKING:
    from app.services.blob_repository import BlobRepository


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


@dataclass(frozen=True)
class MergeResult:
    """Immutable revisions retained for the PR and publication."""

    base: str
    head: str
    commit: str


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
    else:
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
    # One pack for the entire operation, including all rebased commits.
    if write_objects:
        repo.object_store.add_objects([(pending[sha], None) for sha in pending])
    return MergeResult(base.decode(), head.decode(), result.id.decode())
