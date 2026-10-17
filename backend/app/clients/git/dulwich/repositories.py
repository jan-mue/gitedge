"""Dulwich browsing adapter; public methods return application schemas."""

from __future__ import annotations

import asyncio
import io
import logging
import re
import stat
import time
from difflib import SequenceMatcher
from typing import TYPE_CHECKING, Literal, Protocol, cast

from dulwich.annotate import annotate_lines
from dulwich.diff_tree import tree_changes
from dulwich.objects import S_ISGITLINK, Blob, Commit, ObjectID, Tag, Tree
from dulwich.patch import write_object_diff, write_tree_diff
from dulwich.refs import SYMREF, Ref, check_ref_format
from fastapi import HTTPException, status
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, TypeAdapter
from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import TextLexer, get_lexer_for_filename
from pygments.util import ClassNotFound

from app.clients.git.dulwich.activity import collect_git_activity
from app.clients.git.dulwich.diffs import enrich_diff
from app.clients.git.dulwich.http import handle_http
from app.clients.git_refs import GitRefStore
from app.config import settings
from app.schemas.releases import TagInfo, TagsPublic
from app.schemas.repositories import (
    BlameContent,
    BlameLine,
    BranchInfo,
    CommitChangeType,
    CommitDetail,
    CommitFileChange,
    CommitInfo,
    CommitListItem,
    CommitsPublic,
    CompareResult,
    DiffHunk,
    FileContent,
    FileIndex,
    LanguageStatistic,
    ReadmeContent,
    RepositoryInfo,
    RepositoryStatistics,
    TreeEntry,
    TreeEntryType,
    TreeListing,
)
from app.schemas.repository_activity import GitActivityHistory
from app.services.languages import source_language
from app.services.markdown import render_markdown
from app.utils.cache_headers import (
    is_commit_sha,
)

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Iterator

    from dulwich.object_store import BaseObjectStore

    from app.clients.cache import AbstractCacheClient
    from app.clients.git.dulwich.blob_backend import BlobBackend
    from app.clients.git.dulwich.blob_repository import BlobRepository
    from app.clients.git.interfaces import GitHttpRequest, GitHttpResponse
    from app.clients.git.storage import RepositoryStorage

logger = logging.getLogger(__name__)

_README_NAMES = frozenset(
    {
        "README.md",
        "README.MD",
        "readme.md",
        "README",
        "README.txt",
        "README.rst",
        "Readme.md",
    }
)

_DIFF_HEADER_RE = re.compile(r"^diff --git a/(?P<old>.+) b/(?P<new>.+)$")


def _split_author(raw: str) -> tuple[str, str]:
    """Split a raw Git author/committer line into a name and email.

    Git stores authors as ``"Name <email>"``; the email may be empty (``"<>"``).

    Args:
        raw: The raw "Name <email>" value.

    Returns:
        Tuple of (name, email); email is empty when the line does not contain one.
    """
    match = re.match(r"^(?P<name>.*?)\s*<(?P<email>[^>]*)>\s*$", raw)
    if match:
        return match.group("name").strip(), match.group("email").strip()
    return raw.strip(), ""


class StyleDefsProvider(Protocol):
    """Protocol for formatters that expose get_style_defs()."""

    def get_style_defs(self, arg: str = "") -> str:
        """Return the CSS style definitions for the given scope."""


def _get_style_defs(formatter: StyleDefsProvider, arg: str) -> str:
    """Return CSS style definitions for a formatter.

    Args:
        formatter: Pygments formatter.
        arg: CSS scope selector.

    Returns:
        The CSS definitions as a string.
    """
    return formatter.get_style_defs(arg)


def repo_key(owner: str, name: str) -> str:
    """Build the storage key for a repository.

    Args:
        owner: Owner name (user or organization).
        name: Repository name (without the .git suffix).

    Returns:
        The storage key, e.g. "owner/repo.git".
    """
    return f"{owner}/{name}.git"


class DulwichGitClient:
    """Request-scoped Git adapter over shared object and ref storage."""

    def __init__(
        self,
        backend: BlobBackend,
        storage: RepositoryStorage,
        cache_client: AbstractCacheClient,
        repository_exists: Callable[[str, str], Awaitable[bool]],
    ) -> None:
        """Bind storage, derived-response caching, and the empty-repository lookup."""
        self.backend = backend
        self.storage = storage
        self.cache_client = cache_client
        self.repository_exists = repository_exists
        self.git_refs = GitRefStore(storage.redis)

    def _cache_group(self, owner: str, name: str) -> str:
        """Build the cache group for a repository.

        Args:
            owner: Owner name.
            name: Repository name.

        Returns:
            The group used to invalidate a repository's cached responses.
        """
        return f"repo:{owner}/{name}"

    @staticmethod
    def _ttl_for_ref(ref: str) -> int:
        """Pick a cache TTL based on whether a ref is immutable.

        Args:
            ref: Git ref used to address the content.

        Returns:
            The cache TTL in seconds.
        """
        return settings.CACHE_IMMUTABLE_TTL if is_commit_sha(ref) else settings.CACHE_TTL

    async def _cached_model[M: BaseModel](
        self,
        *,
        key: str,
        group: str,
        ttl: int,
        model: type[M],
        compute: Callable[[], Awaitable[M]],
    ) -> M:
        """Return a cached model, computing and storing it on a miss.

        Args:
            key: Cache key within the group.
            group: Group used for bulk invalidation.
            ttl: Time to live in seconds.
            model: Pydantic model type used to (de)serialize the value.
            compute: Coroutine producing the value on a miss.

        Returns:
            The cached or freshly computed model.
        """
        cached = await self.cache_client.get(key, group=group)
        if cached is not None:
            return model.model_validate_json(cached)
        value = await compute()
        await self.cache_client.set(key, value.model_dump_json(), ttl=ttl, group=group)
        return value

    @staticmethod
    def _revision_files(repo: BlobRepository, sha: bytes) -> Iterator[tuple[str, ObjectID]]:
        """Iterate file paths and object IDs, skipping submodules and symlinks."""
        root = DulwichGitClient._get_tree_at_path(repo, sha, "")
        pending = [("", root)]
        while pending:
            prefix, tree = pending.pop()
            for entry in tree.items():
                path = prefix + entry.path.decode("utf-8", errors="replace")
                if stat.S_ISDIR(entry.mode):
                    child = repo.object_store[entry.sha]
                    if isinstance(child, Tree):
                        pending.append((path + "/", child))
                elif stat.S_ISREG(entry.mode):
                    yield path, entry.sha

    @staticmethod
    def _compute_statistics(repo: BlobRepository, sha: bytes) -> RepositoryStatistics:
        """Compute source language shares, total bytes, and reachable commit count."""
        sizes: dict[str, int] = {}
        total = 0
        for path, blob_sha in DulwichGitClient._revision_files(repo, sha):
            blob = repo.object_store[blob_sha]
            if not isinstance(blob, Blob):
                continue
            total += len(blob.data)
            language = source_language(path, blob.data)
            if language:
                sizes[language] = sizes.get(language, 0) + len(blob.data)
        pending = [ObjectID(sha)]
        commits: set[ObjectID] = set()
        while pending:
            commit_sha = pending.pop()
            if commit_sha in commits:
                continue
            commit = repo.object_store[commit_sha]
            if isinstance(commit, Commit):
                commits.add(commit_sha)
                pending.extend(commit.parents)
        source_size = sum(sizes.values())
        return RepositoryStatistics(
            commit_count=len(commits),
            size=total,
            languages=[
                LanguageStatistic(name=language, size=size, percentage=round(size / source_size * 100, 2))
                for language, size in sorted(sizes.items(), key=lambda item: (-item[1], item[0]))
                if size
            ],
        )

    @classmethod
    def _diff_files(
        cls, store: BaseObjectStore, old_tree: ObjectID | None, new_tree: ObjectID, include_diff: bool
    ) -> list[CommitFileChange]:
        """Calculate patches outside the event loop and optionally highlight them."""
        if not include_diff:
            return cls._diff_index(store, old_tree, new_tree)
        buffer = io.BytesIO()
        write_tree_diff(buffer, store, old_tree, new_tree)
        files = cls._parse_patch(buffer.getvalue().decode("utf-8", errors="replace"))
        for file in files:
            hunk_lines = file.patch.split("\n")
            start = next((index for index, line in enumerate(hunk_lines) if line.startswith("@@")), len(hunk_lines))
            file.diff_line_count = sum(line[:1] in (" ", "+", "-") for line in hunk_lines[start:])
            file.additions = sum(line.startswith("+") for line in hunk_lines[start:])
            file.deletions = sum(line.startswith("-") for line in hunk_lines[start:])
            file.is_binary = any(line.startswith("Binary files ") for line in hunk_lines)
            file.diff_loaded = include_diff
        if include_diff:
            enrich_diff(files, store, old_tree, new_tree)
        else:
            for file in files:
                file.patch = ""
        return files

    @staticmethod
    def _diff_index(store: BaseObjectStore, old_tree: ObjectID | None, new_tree: ObjectID) -> list[CommitFileChange]:
        """Count changed ranges directly, without allocating or parsing unified patches."""

        def content(mode: int | None, oid: ObjectID | None) -> bytes:
            if oid is None:
                return b""
            if mode is not None and S_ISGITLINK(mode):
                return b"Subproject commit " + oid + b"\n"
            obj = store[oid]
            return obj.data if isinstance(obj, Blob) else obj.as_raw_string()

        files = []
        statistics: dict[tuple[ObjectID | None, ObjectID | None], tuple[int, int, int, bool]] = {}
        for change in tree_changes(store, old_tree, new_tree):
            old_entry, new_entry = change.old, change.new
            key = (old_entry.sha if old_entry else None, new_entry.sha if new_entry else None)
            if key not in statistics:
                old = content(old_entry.mode, old_entry.sha) if old_entry else b""
                new = content(new_entry.mode, new_entry.sha) if new_entry else b""
                binary = b"\0" in old[:8000] or b"\0" in new[:8000]
                additions = deletions = line_count = 0
                if not binary:
                    matcher = SequenceMatcher(None, old.splitlines(keepends=True), new.splitlines(keepends=True))
                    for group in matcher.get_grouped_opcodes(3):
                        for kind, a, b, c, d in group:
                            if kind != "equal":
                                deletions += b - a
                                additions += d - c
                            line_count += (b - a) if kind == "equal" else (b - a) + (d - c)
                statistics[key] = additions, deletions, line_count, binary
            additions, deletions, line_count, binary = statistics[key]
            entry = new_entry or old_entry
            path = entry.path if entry else None
            if path is None:
                continue
            files.append(
                CommitFileChange(
                    path=path.decode("utf-8", errors="replace"),
                    change_type=CommitChangeType(change.type),
                    additions=additions,
                    deletions=deletions,
                    patch="",
                    diff_loaded=False,
                    diff_line_count=line_count,
                    is_binary=binary,
                )
            )
        return files

    @classmethod
    def _diff_file(
        cls,
        store: BaseObjectStore,
        old_tree: ObjectID | None,
        new_tree: ObjectID,
        path: str,
        anchor: tuple[Literal["old", "new"], int] | None = None,
    ) -> CommitFileChange:
        """Read and diff only the requested path, without diffing sibling files."""

        def entry(tree_id: ObjectID | None) -> tuple[bytes | None, int | None, ObjectID | None]:
            if tree_id is not None:
                tree = store[tree_id]
                if isinstance(tree, Tree):
                    try:
                        mode, oid = tree.lookup_path(store.__getitem__, path.encode())
                    except KeyError:
                        return None, None, None
                    if not stat.S_ISDIR(mode):
                        return path.encode(), mode, oid
            return None, None, None

        old_entry, new_entry = entry(old_tree), entry(new_tree)
        if old_entry == new_entry:
            raise HTTPException(status_code=404, detail="File is not changed in this comparison")
        buffer = io.BytesIO()
        write_object_diff(buffer, store, old_entry, new_entry)
        files = cls._parse_patch(buffer.getvalue().decode("utf-8", errors="replace"))
        enrich_diff(files, store, old_tree, new_tree, anchor)
        file = files[0]
        file.diff_line_count = sum(len(hunk.lines) for hunk in file.hunks)
        file.patch = ""
        return file

    @staticmethod
    def _parse_patch(patch_text: str) -> list[CommitFileChange]:
        """Parse a unified diff into per-file changes.

        Args:
            patch_text: The full unified diff text.

        Returns:
            A CommitFileChange per changed file.
        """
        blocks: list[str] = []
        current: list[str] = []
        for line in patch_text.splitlines():
            if line.startswith("diff --git "):
                if current:
                    blocks.append("\n".join(current))
                current = [line]
            elif current:
                current.append(line)
        if current:
            blocks.append("\n".join(current))

        files: list[CommitFileChange] = []
        for block in blocks:
            lines = block.splitlines()
            match = _DIFF_HEADER_RE.match(lines[0])
            old_path = match.group("old") if match else lines[0]
            new_path = match.group("new") if match else old_path

            change_type = CommitChangeType.MODIFY
            if any(line.startswith("new file mode") for line in lines):
                change_type = CommitChangeType.ADD
            elif any(line.startswith("deleted file mode") for line in lines):
                change_type = CommitChangeType.DELETE
            elif any(line.startswith("rename from") for line in lines):
                change_type = CommitChangeType.RENAME

            for line in lines:
                if line.startswith("rename from "):
                    old_path = line[len("rename from ") :]
                elif line.startswith("rename to "):
                    new_path = line[len("rename to ") :]

            path = old_path if change_type == CommitChangeType.DELETE else new_path
            files.append(
                CommitFileChange(
                    path=path,
                    old_path=old_path if old_path != path else None,
                    change_type=change_type,
                    additions=sum(1 for line in lines if line.startswith("+") and not line.startswith("+++")),
                    deletions=sum(1 for line in lines if line.startswith("-") and not line.startswith("---")),
                    patch=block,
                )
            )

        return files

    @staticmethod
    def _try_resolve_ref(repo: BlobRepository, ref_name: str) -> bytes | None:
        """Resolve a ref name to a commit SHA, or None if the ref is missing.

        Args:
            repo: The repository.
            ref_name: Ref name (e.g., "main", "refs/heads/main").

        Returns:
            The commit SHA as bytes, or None if the ref does not exist.
        """
        refs = repo.refs
        candidates: tuple[str, ...] = (ref_name, f"refs/heads/{ref_name}", f"refs/tags/{ref_name}")
        if ref_name in ("", "HEAD"):
            candidates = (*candidates, "HEAD")

        for candidate in candidates:
            sha = refs.read_loose_ref(Ref(candidate.encode()))
            if sha is not None and sha.startswith(SYMREF):
                sha = refs.read_loose_ref(Ref(sha[len(SYMREF) :]))
            if sha is not None:
                return sha

        if re.fullmatch(r"[0-9a-f]{40}", ref_name):
            oid = ObjectID(ref_name.encode())
            try:
                repo.object_store[oid]
            except KeyError:
                return None
            return oid

        return None

    @staticmethod
    def _resolve_ref(repo: BlobRepository, ref_name: str) -> bytes:
        """Resolve a ref name to a commit SHA.

        Args:
            repo: The repository.
            ref_name: Ref name (e.g., "main", "refs/heads/main").

        Returns:
            The commit SHA as bytes.

        Raises:
            HTTPException: If the ref is not found.
        """
        sha = DulwichGitClient._try_resolve_ref(repo, ref_name)
        if sha is None:
            raise HTTPException(status_code=404, detail=f"Ref '{ref_name}' not found")
        return sha

    @staticmethod
    def _get_tree_at_path(repo: BlobRepository, commit_sha: bytes, path: str) -> Tree:
        """Walk a commit's tree to a specific subdirectory.

        Args:
            repo: The repository.
            commit_sha: The commit SHA.
            path: Path within the repository (e.g., "src/app").

        Returns:
            The Tree object at the given path.

        Raises:
            HTTPException: If the path is not found or not a tree.
        """
        store = repo.object_store
        commit = store[ObjectID(commit_sha)]
        if not isinstance(commit, Commit):
            raise HTTPException(status_code=404, detail="Not a valid commit")

        tree = store[commit.tree]
        if not isinstance(tree, Tree):
            raise HTTPException(status_code=404, detail="Invalid tree")

        if not path or path == "/":
            return tree

        parts = [p for p in path.split("/") if p]
        current_tree = tree

        for part in parts:
            found = False
            for entry in current_tree.items():
                if entry.path.decode() == part:
                    obj = store[entry.sha]
                    if isinstance(obj, Tree):
                        current_tree = obj
                        found = True
                        break
                    raise HTTPException(status_code=400, detail=f"'{part}' is not a directory")
            if not found:
                raise HTTPException(status_code=404, detail=f"Path '{path}' not found")

        return current_tree

    @staticmethod
    def _get_blob_at_path(repo: BlobRepository, commit_sha: bytes, path: str) -> tuple[Blob, str]:
        """Get a file blob at a specific path.

        Args:
            repo: The repository.
            commit_sha: The commit SHA.
            path: File path within the repository.

        Returns:
            Tuple of (Blob object, filename).

        Raises:
            HTTPException: If the file is not found or not a blob.
        """
        store = repo.object_store
        commit = store[ObjectID(commit_sha)]
        if not isinstance(commit, Commit):
            raise HTTPException(status_code=404, detail="Not a valid commit")

        tree = store[commit.tree]
        if not isinstance(tree, Tree):
            raise HTTPException(status_code=404, detail="Invalid tree")

        parts = [p for p in path.split("/") if p]
        if not parts:
            raise HTTPException(status_code=400, detail="Path cannot be empty")

        current_tree = tree
        for part in parts[:-1]:
            found = False
            for entry in current_tree.items():
                if entry.path.decode() == part:
                    obj = store[entry.sha]
                    if isinstance(obj, Tree):
                        current_tree = obj
                        found = True
                        break
                    raise HTTPException(status_code=400, detail=f"'{part}' is not a directory")
            if not found:
                raise HTTPException(status_code=404, detail=f"Path '{path}' not found")

        filename = parts[-1]
        for entry in current_tree.items():
            if entry.path.decode() == filename:
                obj = store[entry.sha]
                if isinstance(obj, Blob):
                    return obj, filename
                raise HTTPException(status_code=400, detail=f"'{filename}' is not a file")

        raise HTTPException(status_code=404, detail=f"File '{path}' not found")

    @staticmethod
    def _get_ref_counts(repo: BlobRepository) -> tuple[int, int, str]:
        """Count branches and tags, and determine the default branch.

        Args:
            repo: The repository.

        Returns:
            Tuple of (branch_count, tag_count, default_branch).
        """
        refs = repo.refs
        all_keys = refs.allkeys()
        branch_count = 0
        tag_count = 0
        default_branch = "main"

        for key in all_keys:
            key_str = key.decode() if isinstance(key, bytes) else str(key)
            if key_str.startswith("refs/heads/"):
                branch_count += 1
            elif key_str.startswith("refs/tags/"):
                tag_count += 1

        head_val = refs.read_loose_ref(Ref(b"HEAD"))
        if head_val is not None and head_val.startswith(SYMREF):
            target = head_val[len(SYMREF) :]
            target_str = target.decode() if isinstance(target, bytes) else str(target)
            if target_str.startswith("refs/heads/"):
                default_branch = target_str[len("refs/heads/") :]

        return branch_count, tag_count, default_branch

    @staticmethod
    def _get_path_commits(repo: BlobRepository, commit_sha: bytes, paths: list[str]) -> dict[str, CommitInfo]:
        """Find each path's last change in one walk, following unchanged merge parents."""
        remaining = set(paths)
        if not remaining:
            return {}
        pending: dict[bytes, set[str]] = {commit_sha: set(paths)}
        result: dict[str, CommitInfo] = {}
        store = repo.object_store

        def path_entry(tree_sha: ObjectID, path: str) -> tuple[int, ObjectID] | None:
            tree = store[tree_sha]
            if not isinstance(tree, Tree):
                return None
            try:
                return tree.lookup_path(store.__getitem__, path.encode())
            except KeyError:
                return None

        for entry in repo.get_walker(include=[ObjectID(commit_sha)], order="topo"):
            commit = entry.commit
            candidates = pending.pop(commit.id, set()) & remaining
            if not candidates:
                continue
            for path in candidates:
                current = path_entry(commit.tree, path)
                unchanged_parents = []
                for parent_sha in commit.parents:
                    parent = store[parent_sha]
                    if isinstance(parent, Commit) and path_entry(parent.tree, path) == current:
                        unchanged_parents.append(parent_sha)
                if unchanged_parents:
                    for parent_sha in unchanged_parents:
                        pending.setdefault(parent_sha, set()).add(path)
                else:
                    result[path] = DulwichGitClient._get_commit_info(repo, commit.id)
                    remaining.remove(path)
            if not remaining:
                break
        return result

    @staticmethod
    def _get_commit_info(repo: BlobRepository, commit_sha: bytes) -> CommitInfo:
        """Extract commit information from a commit SHA.

        Args:
            repo: The repository.
            commit_sha: The commit SHA.

        Returns:
            CommitInfo with the commit details.
        """
        store = repo.object_store
        commit = store[ObjectID(commit_sha)]
        if not isinstance(commit, Commit):
            return CommitInfo(sha="", message="", author="", timestamp=0)

        sha_str = commit_sha.decode() if isinstance(commit_sha, bytes) else str(commit_sha)
        message = commit.message.decode("utf-8", errors="replace").strip()
        author_raw = commit.author.decode("utf-8", errors="replace")
        author = author_raw.split("<")[0].strip() if "<" in author_raw else author_raw
        timestamp = commit.author_time if hasattr(commit, "author_time") else int(time.time())

        return CommitInfo(sha=sha_str, message=message, author=author, timestamp=timestamp)

    @staticmethod
    def _find_readme_in_tree(repo: BlobRepository, tree: Tree) -> tuple[str, str] | None:
        """Find and read a README file in a tree.

        Args:
            repo: The repository.
            tree: The tree to search.

        Returns:
            Tuple of (filename, content) or None if no README was found.
        """
        store = repo.object_store

        for item in tree.items():
            item_name = item.path.decode()
            if item_name in _README_NAMES and not stat.S_ISDIR(item.mode):
                obj = store[item.sha]
                if isinstance(obj, Blob):
                    try:
                        content = obj.data.decode("utf-8")
                    except UnicodeDecodeError:
                        content = "(binary file)"
                    return item_name, content

        return None

    async def get_file_index(self, owner: str, name: str, ref: str) -> FileIndex:
        """Return all searchable file paths at a revision."""

        async def compute() -> FileIndex:
            repo = await self.load_repository(owner, name)
            sha = self._try_resolve_ref(repo, ref)
            if sha is None:
                return FileIndex(paths=[])
            return await run_in_threadpool(
                lambda: FileIndex(paths=sorted(path for path, _ in self._revision_files(repo, sha)))
            )

        return await self._cached_model(
            key=f"files:{ref}",
            group=self._cache_group(owner, name),
            ttl=self._ttl_for_ref(ref),
            model=FileIndex,
            compute=compute,
        )

    async def get_statistics(self, owner: str, name: str, ref: str) -> RepositoryStatistics:
        """Return cached statistics without slowing the source listing."""
        repo = await self.load_repository(owner, name)
        sha = self._try_resolve_ref(repo, ref)
        if sha is None:
            return RepositoryStatistics()

        async def compute() -> RepositoryStatistics:
            return await run_in_threadpool(self._compute_statistics, repo, sha)

        return await self._cached_model(
            key=f"statistics:v2:{sha.decode()}",
            group=self._cache_group(owner, name),
            ttl=settings.CACHE_IMMUTABLE_TTL,
            model=RepositoryStatistics,
            compute=compute,
        )

    async def get_blame(self, owner: str, name: str, ref: str, file_path: str) -> BlameContent:
        """Attribute every file line to its original commit, following renames."""

        async def compute() -> BlameContent:
            repo = await self.load_repository(owner, name)
            sha = self._resolve_ref(repo, ref)
            blob, _ = self._get_blob_at_path(repo, sha, file_path)
            if len(blob.data) > 1024 * 1024:
                raise HTTPException(status_code=413, detail="File is too large for blame (maximum 1 MiB)")
            try:
                blob.data.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise HTTPException(status_code=400, detail="Blame is unavailable for binary files") from exc
            if b"\0" in blob.data:
                raise HTTPException(status_code=400, detail="Blame is unavailable for binary files")
            annotations = await run_in_threadpool(annotate_lines, repo.object_store, ObjectID(sha), file_path.encode())
            return BlameContent(
                path=file_path,
                revision=sha.decode(),
                lines=[
                    BlameLine(
                        number=number,
                        content=line.decode("utf-8", errors="replace").rstrip("\r\n"),
                        commit=self._get_commit_info(repo, commit.id),
                    )
                    for number, ((commit, _), line) in enumerate(annotations, 1)
                ],
            )

        return await self._cached_model(
            key=f"blame:{ref}:{file_path}",
            group=self._cache_group(owner, name),
            ttl=self._ttl_for_ref(ref),
            model=BlameContent,
            compute=compute,
        )

    async def get_raw(self, owner: str, name: str, ref: str, file_path: str) -> bytes:
        """Return a file's original bytes."""
        repo = await self.load_repository(owner, name)
        sha = self._resolve_ref(repo, ref)
        blob, _ = self._get_blob_at_path(repo, sha, file_path)
        return blob.data

    async def get_source(self, owner: str, name: str, ref: str, path: str) -> TreeListing | FileContent:
        """Resolve a source path in one request, avoiding a failed tree request in the browser."""
        try:
            return await self.get_tree(owner, name, ref, path)
        except HTTPException as exc:
            if exc.status_code != status.HTTP_400_BAD_REQUEST:
                raise
            return await self.get_blob(owner, name, ref, path)

    async def get_tree(self, owner: str, name: str, ref: str, tree_path: str) -> TreeListing:
        """Get the directory listing for a repository path.

        Args:
            owner: Owner name.
            name: Repository name.
            ref: Git ref to browse.
            tree_path: Subdirectory path within the repository.

        Returns:
            TreeListing with the directory entries.
        """

        async def compute() -> TreeListing:
            repo = await self.load_repository(owner, name)
            commit_sha = self._resolve_ref(repo, ref)
            tree = self._get_tree_at_path(repo, commit_sha, tree_path)

            entries: list[TreeEntry] = []
            store = repo.object_store
            paths = [f"{tree_path}/{item.path.decode()}".lstrip("/") for item in tree.items()]
            last_commits = await run_in_threadpool(self._get_path_commits, repo, commit_sha, paths)

            for item in sorted(tree.items(), key=lambda e: (not stat.S_ISDIR(e.mode), e.path)):
                entry_name = item.path.decode()
                entry_path = f"{tree_path}/{entry_name}".lstrip("/") if tree_path else entry_name
                is_dir = stat.S_ISDIR(item.mode)

                size = None
                if not is_dir:
                    obj = store[item.sha]
                    if isinstance(obj, Blob):
                        size = len(obj.data)

                entries.append(
                    TreeEntry(
                        name=entry_name,
                        path=entry_path,
                        type=TreeEntryType.TREE if is_dir else TreeEntryType.BLOB,
                        size=size,
                        last_commit=last_commits.get(entry_path),
                    )
                )

            return TreeListing(entries=entries, tree_path=tree_path, ref=ref)

        return await self._cached_model(
            key=f"tree:v2:{ref}:{tree_path}",
            group=self._cache_group(owner, name),
            ttl=self._ttl_for_ref(ref),
            model=TreeListing,
            compute=compute,
        )

    async def get_blob(self, owner: str, name: str, ref: str, file_path: str) -> FileContent:
        """Get file content with syntax highlighting.

        Args:
            owner: Owner name.
            name: Repository name.
            ref: Git ref.
            file_path: File path within the repository.

        Returns:
            FileContent with highlighted HTML and CSS.

        Raises:
            HTTPException: If file_path is empty.
        """
        if not file_path:
            raise HTTPException(status_code=400, detail="file_path is required")

        async def compute() -> FileContent:
            repo = await self.load_repository(owner, name)
            commit_sha = self._resolve_ref(repo, ref)
            blob, filename = self._get_blob_at_path(repo, commit_sha, file_path)

            raw_data = blob.data
            try:
                content = raw_data.decode("utf-8")
            except UnicodeDecodeError:
                content = "(binary file)"

            try:
                lexer = get_lexer_for_filename(filename)
            except ClassNotFound:
                lexer = TextLexer()

            formatter = HtmlFormatter(
                style="default",
                cssclass="highlight",
                linenos="table",
                lineanchors="L",
                anchorlinenos=True,
                wrapcode=True,
            )

            # Create dark mode formatter for CSS only (same HTML, different colors)
            dark_formatter = HtmlFormatter(
                style="github-dark",
                cssclass="highlight",
            )

            highlighted_html = cast(str, await run_in_threadpool(highlight, content, lexer, formatter))
            css = _get_style_defs(formatter, ".highlight")

            # Scope all dark CSS rules under .dark to prevent them from leaking into
            # light mode. get_style_defs() only prefixes .highlight rules, but Pygments
            # also emits global rules (td.linenos, span.linenos, pre) that need scoping.
            raw_dark_css = _get_style_defs(dark_formatter, ".highlight")
            css_dark = "\n".join(
                f".dark {line}" if line and not line.startswith(".dark") else line for line in raw_dark_css.split("\n")
            )
            line_count = content.count("\n") + (1 if content and not content.endswith("\n") else 0)
            last_commits = await run_in_threadpool(self._get_path_commits, repo, commit_sha, [file_path])

            return FileContent(
                name=filename,
                path=file_path,
                size=len(raw_data),
                content=content,
                highlighted_html=highlighted_html,
                css=css,
                css_dark=css_dark,
                language=lexer.name,
                line_count=line_count,
                last_commit=last_commits.get(file_path),
            )

        return await self._cached_model(
            key=f"blob:v2:{ref}:{file_path}",
            group=self._cache_group(owner, name),
            ttl=self._ttl_for_ref(ref),
            model=FileContent,
            compute=compute,
        )

    async def get_info(self, owner: str, name: str, ref: str) -> RepositoryInfo:
        """Get extended repository information.

        Includes branch/tag counts, default branch, and last commit info.

        Args:
            owner: Owner name.
            name: Repository name.
            ref: Git ref.

        Returns:
            RepositoryInfo with metadata.
        """

        async def compute() -> RepositoryInfo:
            repo = await self.load_repository(owner, name)

            branch_count, tag_count, default_branch = self._get_ref_counts(repo)

            commit_sha = self._try_resolve_ref(repo, ref)
            last_commit = self._get_commit_info(repo, commit_sha) if commit_sha is not None else None

            return RepositoryInfo(
                name=name,
                owner=owner,
                default_branch=default_branch,
                branch_count=branch_count,
                tag_count=tag_count,
                last_commit=last_commit,
            )

        return await self._cached_model(
            key=f"git-info:v1:{ref}",
            group=self._cache_group(owner, name),
            ttl=settings.CACHE_TTL,
            model=RepositoryInfo,
            compute=compute,
        )

    async def get_readme(self, owner: str, name: str, ref: str, tree_path: str) -> ReadmeContent:
        """Get the README content from a repository directory.

        Args:
            owner: Owner name.
            name: Repository name.
            ref: Git ref.
            tree_path: Subdirectory path within the repository.

        Returns:
            ReadmeContent with the filename, raw content and rendered HTML.

        Raises:
            HTTPException: If no README is found.
        """

        async def compute() -> ReadmeContent:
            repo = await self.load_repository(owner, name)
            commit_sha = self._resolve_ref(repo, ref)
            tree = self._get_tree_at_path(repo, commit_sha, tree_path)

            result = self._find_readme_in_tree(repo, tree)
            if result is None:
                raise HTTPException(status_code=404, detail="README not found")

            filename, content = result
            html = render_markdown(content) if filename.lower().endswith((".md", ".markdown")) else ""
            return ReadmeContent(filename=filename, content=content, html=html)

        return await self._cached_model(
            key=f"readme:{ref}:{tree_path}",
            group=self._cache_group(owner, name),
            ttl=self._ttl_for_ref(ref),
            model=ReadmeContent,
            compute=compute,
        )

    async def list_branches(self, owner: str, name: str) -> list[BranchInfo]:
        """List all branches in a repository.

        Args:
            owner: Owner name.
            name: Repository name.

        Returns:
            List of BranchInfo with branch names and default flag.
        """
        group = self._cache_group(owner, name)
        adapter: TypeAdapter[list[BranchInfo]] = TypeAdapter(list[BranchInfo])
        cached = await self.cache_client.get("branches", group=group)
        if cached is not None:
            return adapter.validate_json(cached)

        repo = await self.load_repository(owner, name)
        refs = repo.refs
        all_keys = refs.allkeys()

        default_branch = "main"
        head_val = refs.read_loose_ref(Ref(b"HEAD"))
        if head_val is not None and head_val.startswith(SYMREF):
            target = head_val[len(SYMREF) :]
            target_str = target.decode() if isinstance(target, bytes) else str(target)
            if target_str.startswith("refs/heads/"):
                default_branch = target_str[len("refs/heads/") :]

        branches: list[BranchInfo] = []
        for key in sorted(all_keys):
            key_str = key.decode() if isinstance(key, bytes) else str(key)
            if key_str.startswith("refs/heads/"):
                branch_name = key_str[len("refs/heads/") :]
                branches.append(BranchInfo(name=branch_name, is_default=branch_name == default_branch))

        await self.cache_client.set(
            "branches", adapter.dump_json(branches).decode(), ttl=settings.CACHE_TTL, group=group
        )
        return branches

    async def list_tags(self, owner: str, name: str) -> TagsPublic:
        """List all tags in a repository.

        Args:
            owner: Owner name.
            name: Repository name.

        Returns:
            TagsPublic with tag names, target commit SHAs and timestamps.
        """

        async def compute() -> TagsPublic:
            repo = await self.load_repository(owner, name)
            refs = repo.refs
            store = repo.object_store

            tags: list[TagInfo] = []
            for key in sorted(refs.allkeys()):
                key_str = key.decode() if isinstance(key, bytes) else str(key)
                if not key_str.startswith("refs/tags/"):
                    continue
                tag_name = key_str[len("refs/tags/") :]
                sha = refs.read_loose_ref(Ref(key if isinstance(key, bytes) else key.encode()))
                if sha is None:
                    continue

                commit_sha = sha
                timestamp: int | None = None
                obj = store[ObjectID(sha)]
                if isinstance(obj, Tag):
                    commit_sha = obj.object[1]
                    timestamp = obj.tag_time
                commit_obj = store[ObjectID(commit_sha)]
                if isinstance(commit_obj, Commit) and timestamp is None:
                    timestamp = commit_obj.commit_time

                sha_str = commit_sha.decode() if isinstance(commit_sha, bytes) else str(commit_sha)
                tags.append(TagInfo(name=tag_name, commit_sha=sha_str, timestamp=timestamp))

            tags.sort(key=lambda tag: tag.name, reverse=True)
            return TagsPublic(data=tags, count=len(tags))

        return await self._cached_model(
            key="tags",
            group=self._cache_group(owner, name),
            ttl=settings.CACHE_TTL,
            model=TagsPublic,
            compute=compute,
        )

    async def activity_history(self, owner: str, name: str) -> GitActivityHistory:
        """Get cached, complete activity statistics for the repository's branches."""

        async def compute() -> GitActivityHistory:
            repo = await self.load_repository(owner, name)
            _, _, default_branch = self._get_ref_counts(repo)
            return await asyncio.to_thread(collect_git_activity, repo, default_branch)

        return await self._cached_model(
            key="activity-history:v1",
            group=self._cache_group(owner, name),
            ttl=settings.CACHE_TTL,
            model=GitActivityHistory,
            compute=compute,
        )

    async def list_commits(
        self, owner: str, name: str, ref: str = "main", offset: int = 0, limit: int = 50, file_path: str = ""
    ) -> CommitsPublic:
        """List commits reachable from a ref, newest first.

        Args:
            owner: Owner name.
            name: Repository name.
            ref: Git ref to start the history from.
            offset: Number of commits to skip.
            limit: Maximum number of commits to return.
            file_path: Optional path whose history to return.

        Returns:
            CommitsPublic with the requested page of commits.
        """

        async def compute() -> CommitsPublic:
            repo = await self.load_repository(owner, name)
            commit_sha = self._try_resolve_ref(repo, ref)
            if commit_sha is None:
                return CommitsPublic(data=[], count=0, ref=ref)

            data: list[CommitListItem] = []
            skipped = 0
            for entry in repo.get_walker(
                include=[ObjectID(commit_sha)], paths=[file_path.encode()] if file_path else None
            ):
                if skipped < offset:
                    skipped += 1
                    continue
                if len(data) >= limit:
                    break

                commit = entry.commit
                sha = commit.id.decode() if isinstance(commit.id, bytes) else str(commit.id)
                author, author_email = _split_author(commit.author.decode("utf-8", errors="replace"))
                data.append(
                    CommitListItem(
                        sha=sha,
                        message=commit.message.decode("utf-8", errors="replace").strip(),
                        author=author,
                        author_email=author_email,
                        timestamp=commit.author_time,
                    )
                )

            return CommitsPublic(data=data, count=len(data), ref=ref)

        return await self._cached_model(
            key=f"commits:{ref}:{offset}:{limit}:{file_path}",
            group=self._cache_group(owner, name),
            ttl=self._ttl_for_ref(ref),
            model=CommitsPublic,
            compute=compute,
        )

    async def get_commit(self, owner: str, name: str, sha: str, *, include_diff: bool = True) -> CommitDetail:
        """Get detailed information about a single commit, including its diff.

        Args:
            owner: Owner name.
            name: Repository name.
            sha: Full commit SHA.
            include_diff: Include highlighted hunks, or return a compact file index.

        Returns:
            CommitDetail with metadata and per-file unified diffs.

        Raises:
            HTTPException: If the commit is not found.
        """

        async def compute() -> CommitDetail:
            repo = await self.load_repository(owner, name)
            store = repo.object_store
            try:
                obj = store[ObjectID(sha.encode())]
            except (KeyError, ValueError) as e:
                raise HTTPException(status_code=404, detail="Commit not found") from e
            if not isinstance(obj, Commit):
                raise HTTPException(status_code=404, detail="Commit not found")

            parent = store[obj.parents[0]] if obj.parents else None
            files = await run_in_threadpool(
                self._diff_files, store, parent.tree if isinstance(parent, Commit) else None, obj.tree, include_diff
            )

            author, author_email = _split_author(obj.author.decode("utf-8", errors="replace"))
            sha_str = obj.id.decode() if isinstance(obj.id, bytes) else str(obj.id)
            return CommitDetail(
                sha=sha_str,
                message=obj.message.decode("utf-8", errors="replace").strip(),
                author=author,
                author_email=author_email,
                timestamp=obj.author_time,
                parents=[p.decode() if isinstance(p, bytes) else str(p) for p in obj.parents],
                files=files,
                additions=sum(file.additions for file in files),
                deletions=sum(file.deletions for file in files),
            )

        return await self._cached_model(
            key=f"commit:v4:{sha}:{include_diff}",
            group=self._cache_group(owner, name),
            ttl=settings.CACHE_IMMUTABLE_TTL,
            model=CommitDetail,
            compute=compute,
        )

    async def branch_heads(self, owner: str, name: str, base: str, head: str) -> tuple[str | None, str | None]:
        """Read two branch tips without opening packs, walking history, or calculating a diff."""
        return await self.git_refs.branch_heads(owner, name, base, head)

    async def compare_commits(
        self, owner: str, name: str, base_ref: str, head_ref: str, offset: int = 0, limit: int = 50
    ) -> CommitsPublic:
        """List only commits reachable from the head and absent from the base, with pagination."""

        async def compute() -> CommitsPublic:
            repo = await self.load_repository(owner, name)
            base = self._try_resolve_ref(repo, base_ref)
            head = self._try_resolve_ref(repo, head_ref)
            if base is None or head is None:
                return CommitsPublic(data=[], count=0, ref=head_ref)

            def walk() -> CommitsPublic:
                commits = []
                count = 0
                for entry in repo.get_walker(include=[ObjectID(head)], exclude=[ObjectID(base)]):
                    if offset <= count < offset + limit:
                        commit = entry.commit
                        author, email = _split_author(commit.author.decode("utf-8", errors="replace"))
                        commits.append(
                            CommitListItem(
                                sha=commit.id.decode(),
                                message=commit.message.decode("utf-8", errors="replace").strip(),
                                author=author,
                                author_email=email,
                                timestamp=commit.author_time,
                            )
                        )
                    count += 1
                return CommitsPublic(data=commits, count=count, ref=head_ref)

            return await run_in_threadpool(walk)

        return await self._cached_model(
            key=f"compare-commits:v1:{base_ref}:{head_ref}:{offset}:{limit}",
            group=self._cache_group(owner, name),
            ttl=settings.CACHE_TTL,
            model=CommitsPublic,
            compute=compute,
        )

    async def compare(
        self, owner: str, name: str, base_ref: str, head_ref: str, *, include_diff: bool = True
    ) -> CompareResult:
        """List the files changed between two refs.

        Args:
            owner: Owner name.
            name: Repository name.
            base_ref: Base ref (branch, tag, or commit SHA).
            head_ref: Head ref (branch, tag, or commit SHA).
            include_diff: Include highlighted hunks, or return a compact file index.

        Returns:
            CompareResult with the changed files and the resolved head commit.
        """

        async def compute() -> CompareResult:
            repo = await self.load_repository(owner, name)
            base_sha = self._try_resolve_ref(repo, base_ref)
            head_sha = self._try_resolve_ref(repo, head_ref)
            if base_sha is None or head_sha is None:
                return CompareResult(files=[], additions=0, deletions=0)

            store = repo.object_store
            base_commit = store[ObjectID(base_sha)]
            head_commit = store[ObjectID(head_sha)]
            if not isinstance(base_commit, Commit) or not isinstance(head_commit, Commit):
                return CompareResult(files=[], additions=0, deletions=0)

            files = await run_in_threadpool(self._diff_files, store, base_commit.tree, head_commit.tree, include_diff)

            base_str = base_commit.id.decode() if isinstance(base_commit.id, bytes) else str(base_commit.id)
            head_str = head_commit.id.decode() if isinstance(head_commit.id, bytes) else str(head_commit.id)
            return CompareResult(
                base_commit=base_str,
                head_commit=head_str,
                files=files,
                additions=sum(file.additions for file in files),
                deletions=sum(file.deletions for file in files),
            )

        ttl = (
            settings.CACHE_IMMUTABLE_TTL if is_commit_sha(base_ref) and is_commit_sha(head_ref) else settings.CACHE_TTL
        )
        return await self._cached_model(
            key=f"compare:v4:{base_ref}:{head_ref}:{include_diff}",
            group=self._cache_group(owner, name),
            ttl=ttl,
            model=CompareResult,
            compute=compute,
        )

    async def get_diff_file(self, owner: str, name: str, head: str, file_path: str, base: str = "") -> CommitFileChange:
        """Return one highlighted file at immutable comparison revisions."""

        async def compute() -> CommitFileChange:
            repo = await self.load_repository(owner, name)
            store = repo.object_store
            try:
                head_commit = store[ObjectID(head.encode())]
                base_commit = store[ObjectID(base.encode())] if base else None
            except (KeyError, ValueError) as error:
                raise HTTPException(status_code=404, detail="Comparison revision not found") from error
            if not isinstance(head_commit, Commit) or (base_commit is not None and not isinstance(base_commit, Commit)):
                raise HTTPException(status_code=404, detail="Comparison revision not found")
            old_tree = base_commit.tree if isinstance(base_commit, Commit) else None
            return await run_in_threadpool(self._diff_file, store, old_tree, head_commit.tree, file_path)

        return await self._cached_model(
            key=f"diff-file:v2:{base}:{head}:{file_path}",
            group=self._cache_group(owner, name),
            ttl=settings.CACHE_IMMUTABLE_TTL,
            model=CommitFileChange,
            compute=compute,
        )

    async def get_diff_context(
        self, owner: str, name: str, base: str, head: str, path: str, side: Literal["old", "new"], line: int
    ) -> DiffHunk:
        """Highlight and transfer only the bounded context needed for one legacy review comment."""

        async def compute() -> DiffHunk:
            repo = await self.load_repository(owner, name)
            store = repo.object_store
            try:
                before, after = store[ObjectID(base.encode())], store[ObjectID(head.encode())]
            except KeyError as error:
                raise HTTPException(status_code=404, detail="Comparison revision not found") from error
            if not isinstance(before, Commit) or not isinstance(after, Commit):
                raise HTTPException(status_code=404, detail="Comparison revision not found")
            file = await run_in_threadpool(self._diff_file, store, before.tree, after.tree, path, (side, line))
            if not file.hunks:
                raise HTTPException(status_code=404, detail="Diff context is unavailable for this line")
            return file.hunks[0]

        return await self._cached_model(
            key=f"review-context:v1:{base}:{head}:{path}:{side}:{line}",
            group=self._cache_group(owner, name),
            ttl=settings.CACHE_IMMUTABLE_TTL,
            model=DiffHunk,
            compute=compute,
        )

    async def load_repository(self, owner: str, name: str) -> BlobRepository:
        """Load a repository from storage.

        Args:
            owner: Owner name.
            name: Repository name.

        Returns:
            The loaded repository.

        Raises:
            HTTPException: If the repository does not exist.
        """
        key = repo_key(owner, name)
        logger.debug("Loading repository: %s", key)

        if self.backend.repository_exists(key):
            logger.debug("Repository found in cache: %s", key)
            return self.backend.open_repository(key)

        packs, refs = await self.storage.load(key)
        logger.debug("Loaded from storage: %s (packs=%d, refs=%d)", key, len(packs), len(refs))
        if packs or refs:
            return self.backend.load_repository_from_data(key, packs, refs)

        # A row without stored Git data is an empty repository, not a missing one.
        if await self.repository_exists(owner, name):
            return self.backend.create_repository(key)
        raise HTTPException(status_code=404, detail="Repository not found")

    async def save_changes(self, owner: str, name: str) -> None:
        """Persist pending repository changes to storage.

        Args:
            owner: Owner name.
            name: Repository name.
        """
        key = repo_key(owner, name)
        changes = self.backend.get_repository_changes(key)
        if not any(changes.values()):
            return

        await self.storage.save(key, changes)
        self.backend.clear_repository_changes(key)
        await self.cache_client.invalidate(self._cache_group(owner, name))

    async def create_repository(self, owner: str, name: str) -> None:
        """Create and persist a bare repository's HEAD."""
        self.backend.create_repository(repo_key(owner, name))
        await self.save_changes(owner, name)

    async def ensure_loaded(self, owner: str, name: str) -> None:
        """Load an existing repository, or initialize an empty metadata row."""
        await self.load_repository(owner, name)

    async def set_default_branch(self, owner: str, name: str, branch_name: str) -> None:
        """Validate a branch and update the symbolic HEAD."""
        repo = await self.load_repository(owner, name)
        branch = Ref(f"refs/heads/{branch_name}".encode())
        if not check_ref_format(branch):
            raise HTTPException(status_code=400, detail="Invalid branch name")
        if repo.refs.allkeys() - {Ref(b"HEAD")} and branch not in repo.refs.allkeys():
            raise HTTPException(status_code=400, detail="Default branch must exist")
        repo.refs.set_symbolic_ref(Ref(b"HEAD"), branch)
        await self.save_changes(owner, name)

    async def copy_repository(self, owner: str, name: str, target_owner: str, target_name: str) -> None:
        """Copy persisted objects and refs, evicting any loaded destination."""
        await self.storage.copy(repo_key(owner, name), repo_key(target_owner, target_name))
        self.backend.remove_repository(repo_key(target_owner, target_name))

    async def delete_repository(self, owner: str, name: str) -> None:
        """Remove persisted objects, refs, and the request-local repository."""
        await self.storage.delete(repo_key(owner, name))
        self.backend.remove_repository(repo_key(owner, name))

    async def handle_http(self, request: GitHttpRequest) -> GitHttpResponse:
        """Run synchronous protocol processing off the event loop."""
        return await run_in_threadpool(handle_http, self.backend, request)
