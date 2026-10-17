"""Application Git contracts. No engine objects or storage SDK types cross this boundary."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal, Protocol

if TYPE_CHECKING:
    import uuid

    from app.schemas.releases import TagsPublic
    from app.schemas.repositories import (
        BlameContent,
        BranchInfo,
        CommitDetail,
        CommitFileChange,
        CommitsPublic,
        CompareResult,
        DiffHunk,
        FileContent,
        FileIndex,
        MergeMessage,
        MergeMethod,
        PullRequestMergeability,
        ReadmeContent,
        RepositoryInfo,
        RepositoryStatistics,
        TreeListing,
    )
    from app.schemas.repository_activity import GitActivityHistory


@dataclass(frozen=True)
class GitHttpRequest:
    """Decoded HTTP input for a Git engine's smart/dumb HTTP implementation."""

    method: str
    path: str
    query: str
    headers: dict[str, str]
    body: bytes
    scheme: str = "http"
    hostname: str = "localhost"
    port: int = 80


@dataclass(frozen=True)
class GitHttpResponse:
    """Buffered Git protocol output, independent of the web framework."""

    body: bytes
    status: int
    headers: dict[str, str]


@dataclass(frozen=True)
class MergeResult:
    """Immutable revisions retained for publication and recovery."""

    base: str
    head: str
    commit: str


@dataclass(frozen=True)
class MergeRequest:
    """Validated merge policy and user input passed to a Git engine."""

    owner: str
    name: str
    number: int
    pull_id: uuid.UUID
    base_branch: str
    head_branch: str
    method: MergeMethod
    template: MergeMessage
    title: str
    body: str | None
    identity: bytes
    delete_branch: bool
    expected_base: str | None = None
    expected_head: str | None = None


class GitMergeClient(Protocol):
    """Merge calculation and atomic publication, without native repository handles."""

    async def completed(self, owner: str, name: str, pull_id: uuid.UUID) -> MergeResult | None:
        """Recover a previously published merge."""
        ...

    async def check(self, owner: str, name: str, base: str, head: str, method: MergeMethod) -> PullRequestMergeability:
        """Calculate mergeability for immutable tips."""
        ...

    async def merge(self, request: MergeRequest) -> MergeResult:
        """Calculate and durably publish a merge, rejecting changed tips."""
        ...


class GitClient(Protocol):
    """Repository operations exposed to services; implementations own all native state."""

    async def create_repository(self, owner: str, name: str) -> None:
        """Initialize persisted Git storage."""
        ...

    async def ensure_loaded(self, owner: str, name: str) -> None:
        """Prepare a repository for a Git protocol request."""
        ...

    async def save_changes(self, owner: str, name: str) -> None:
        """Persist any staged changes."""
        ...

    async def set_default_branch(self, owner: str, name: str, branch_name: str) -> None:
        """Validate and update HEAD."""
        ...

    async def copy_repository(self, owner: str, name: str, target_owner: str, target_name: str) -> None:
        """Copy persisted objects and refs."""
        ...

    async def delete_repository(self, owner: str, name: str) -> None:
        """Remove persisted data and local state."""
        ...

    async def handle_http(self, request: GitHttpRequest) -> GitHttpResponse:
        """Serve Git protocol input using the engine's native HTTP implementation."""
        ...

    async def get_file_index(self, owner: str, name: str, ref: str) -> FileIndex:
        """Return engine-neutral get file index."""
        ...

    async def get_statistics(self, owner: str, name: str, ref: str) -> RepositoryStatistics:
        """Return engine-neutral get statistics."""
        ...

    async def get_blame(self, owner: str, name: str, ref: str, file_path: str) -> BlameContent:
        """Return engine-neutral get blame."""
        ...

    async def get_raw(self, owner: str, name: str, ref: str, file_path: str) -> bytes:
        """Return engine-neutral get raw."""
        ...

    async def get_source(self, owner: str, name: str, ref: str, path: str) -> TreeListing | FileContent:
        """Return engine-neutral get source."""
        ...

    async def get_tree(self, owner: str, name: str, ref: str, tree_path: str) -> TreeListing:
        """Return engine-neutral get tree."""
        ...

    async def get_blob(self, owner: str, name: str, ref: str, file_path: str) -> FileContent:
        """Return engine-neutral get blob."""
        ...

    async def get_info(self, owner: str, name: str, ref: str) -> RepositoryInfo:
        """Return engine-neutral get info."""
        ...

    async def get_readme(self, owner: str, name: str, ref: str, tree_path: str) -> ReadmeContent:
        """Return engine-neutral get readme."""
        ...

    async def list_branches(self, owner: str, name: str) -> list[BranchInfo]:
        """Return engine-neutral list branches."""
        ...

    async def list_tags(self, owner: str, name: str) -> TagsPublic:
        """Return engine-neutral list tags."""
        ...

    async def activity_history(self, owner: str, name: str) -> GitActivityHistory:
        """Return engine-neutral activity history."""
        ...

    async def list_commits(
        self, owner: str, name: str, ref: str = "main", offset: int = 0, limit: int = 50, file_path: str = ""
    ) -> CommitsPublic:
        """Return engine-neutral list commits."""
        ...

    async def get_commit(self, owner: str, name: str, sha: str, *, include_diff: bool = True) -> CommitDetail:
        """Return engine-neutral get commit."""
        ...

    async def branch_heads(self, owner: str, name: str, base: str, head: str) -> tuple[str | None, str | None]:
        """Return engine-neutral branch heads."""
        ...

    async def compare_commits(
        self, owner: str, name: str, base_ref: str, head_ref: str, offset: int = 0, limit: int = 50
    ) -> CommitsPublic:
        """Return engine-neutral compare commits."""
        ...

    async def compare(
        self, owner: str, name: str, base_ref: str, head_ref: str, *, include_diff: bool = True
    ) -> CompareResult:
        """Return engine-neutral compare."""
        ...

    async def get_diff_file(self, owner: str, name: str, head: str, file_path: str, base: str = "") -> CommitFileChange:
        """Return engine-neutral get diff file."""
        ...

    async def get_diff_context(
        self, owner: str, name: str, base: str, head: str, path: str, side: Literal["old", "new"], line: int
    ) -> DiffHunk:
        """Return engine-neutral get diff context."""
        ...
