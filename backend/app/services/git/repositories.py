"""Git repository browsing and storage operations."""

from __future__ import annotations

import io
import logging
import re
import stat
import time
from difflib import SequenceMatcher
from typing import TYPE_CHECKING, Literal

from dulwich.annotate import annotate_lines
from dulwich.diff_tree import tree_changes
from dulwich.objects import S_ISGITLINK, Blob, Commit, ObjectID, Tag, Tree
from dulwich.patch import write_object_diff, write_tree_diff
from dulwich.refs import SYMREF, Ref, check_ref_format
from dulwich.server import DictBackend
from fastapi import HTTPException, status
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, TypeAdapter
from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import TextLexer, get_lexer_for_filename
from pygments.util import ClassNotFound

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
from app.services.git.http import handle_http
from app.services.git.repository import BlobRepository
from app.utils.cache_headers import (
    is_commit_sha,
)
from app.utils.diffs import enrich_diff
from app.utils.languages import source_language
from app.utils.markdown import render_markdown
from app.utils.repository_activity import collect_git_activity

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

    from dulwich.object_store import BaseObjectStore

    from app.clients.cache import AbstractCacheClient
    from app.clients.git import GitStore
    from app.clients.repositories import RepositoryStore
    from app.types import GitHttpRequest, GitHttpResponse

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


def repo_key(owner: str, name: str) -> str:
    """Build the storage key for a repository.

    Args:
        owner: Owner name (user or organization).
        name: Repository name (without the .git suffix).

    Returns:
        The storage key, e.g. "owner/repo.git".
    """
    return f"{owner}/{name}.git"


class GitService:
    """Request-scoped Git service over shared object and ref storage."""

    def __init__(
        self,
        storage: GitStore,
        cache_client: AbstractCacheClient,
        repository_store: RepositoryStore,
    ) -> None:
        """Bind storage, derived-response caching, and the empty-repository lookup."""
        self.repositories: dict[str, BlobRepository] = {}
        self.storage = storage
        self.cache_client = cache_client
        self.repository_store = repository_store

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
        ttl: int,
        model: type[M],
        compute: Callable[[BlobRepository], M],
        owner: str,
        name: str,
    ) -> M:
        """Return a cached model, computing and storing it on a miss.

        Args:
            key: Cache key within the group.
            ttl: Time to live in seconds.
            model: Pydantic model type used to (de)serialize the value.
            compute: Synchronous Git operation to run in a worker on a miss.
            owner: Repository owner.
            name: Repository name.

        Returns:
            The cached or freshly computed model.
        """
        group = self._cache_group(owner, name)
        cached = await self.cache_client.get(key, group=group)
        if cached is not None:
            return model.model_validate_json(cached)
        repo = await self.load_repository(owner, name)
        value = await run_in_threadpool(compute, repo)
        await self.cache_client.set(key, value.model_dump_json(), ttl=ttl, group=group)
        return value

    @staticmethod
    def _revision_files(repo: BlobRepository, sha: bytes) -> Iterator[tuple[str, ObjectID]]:
        """Iterate file paths and object IDs, skipping submodules and symlinks."""
        root = GitService._get_tree_at_path(repo, sha, "")
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
        for path, blob_sha in GitService._revision_files(repo, sha):
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
        sha = GitService._try_resolve_ref(repo, ref_name)
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
                    result[path] = GitService._get_commit_info(repo, commit.id)
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

        def compute(repo: BlobRepository) -> FileIndex:
            sha = self._try_resolve_ref(repo, ref)
            if sha is None:
                return FileIndex(paths=[])
            return FileIndex(paths=sorted(path for path, _ in self._revision_files(repo, sha)))

        return await self._cached_model(
            key=f"files:{ref}",
            ttl=self._ttl_for_ref(ref),
            model=FileIndex,
            compute=compute,
            owner=owner,
            name=name,
        )

    async def get_statistics(self, owner: str, name: str, ref: str) -> RepositoryStatistics:
        """Return cached statistics without slowing the source listing."""
        repo = await self.load_repository(owner, name)
        sha = await run_in_threadpool(self._try_resolve_ref, repo, ref)
        if sha is None:
            return RepositoryStatistics()

        def compute(repo: BlobRepository) -> RepositoryStatistics:
            return self._compute_statistics(repo, sha)

        return await self._cached_model(
            key=f"statistics:v2:{sha.decode()}",
            ttl=settings.CACHE_IMMUTABLE_TTL,
            model=RepositoryStatistics,
            compute=compute,
            owner=owner,
            name=name,
        )

    async def get_blame(self, owner: str, name: str, ref: str, file_path: str) -> BlameContent:
        """Attribute every file line to its original commit, following renames."""

        def compute(repo: BlobRepository) -> BlameContent:
            sha = self._resolve_ref(repo, ref)
            blob, _ = self._get_blob_at_path(repo, sha, file_path)
            if len(blob.data) > 1024 * 1024:
                raise HTTPException(status_code=413, detail="File is too large for blame (maximum 1 MiB)")
            try:
                blob.data.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise HTTPException(status_code=400, detail="Blame is unavailable for binary files") from exc
            if b"\x00" in blob.data:
                raise HTTPException(status_code=400, detail="Blame is unavailable for binary files")
            annotations = annotate_lines(repo.object_store, ObjectID(sha), file_path.encode())
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
            ttl=self._ttl_for_ref(ref),
            model=BlameContent,
            compute=compute,
            owner=owner,
            name=name,
        )

    async def get_raw(self, owner: str, name: str, ref: str, file_path: str) -> bytes:
        """Return a file's original bytes."""
        repo = await self.load_repository(owner, name)

        def read() -> bytes:
            sha = self._resolve_ref(repo, ref)
            blob, _ = self._get_blob_at_path(repo, sha, file_path)
            return blob.data

        return await run_in_threadpool(read)

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

        def compute(repo: BlobRepository) -> TreeListing:
            commit_sha = self._resolve_ref(repo, ref)
            tree = self._get_tree_at_path(repo, commit_sha, tree_path)
            entries: list[TreeEntry] = []
            store = repo.object_store
            paths = [f"{tree_path}/{item.path.decode()}".lstrip("/") for item in tree.items()]
            last_commits = self._get_path_commits(repo, commit_sha, paths)
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
            ttl=self._ttl_for_ref(ref),
            model=TreeListing,
            compute=compute,
            owner=owner,
            name=name,
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

        def compute(repo: BlobRepository) -> FileContent:
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
            dark_formatter = HtmlFormatter(style="github-dark", cssclass="highlight")
            highlighted_html = highlight(content, lexer, formatter)
            css = formatter.get_style_defs(".highlight")
            raw_dark_css = dark_formatter.get_style_defs(".highlight")
            css_dark = "\n".join(
                f".dark {line}" if line and (not line.startswith(".dark")) else line
                for line in raw_dark_css.split("\n")
            )
            line_count = content.count("\n") + (1 if content and (not content.endswith("\n")) else 0)
            last_commits = self._get_path_commits(repo, commit_sha, [file_path])
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
            ttl=self._ttl_for_ref(ref),
            model=FileContent,
            compute=compute,
            owner=owner,
            name=name,
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

        def compute(repo: BlobRepository) -> RepositoryInfo:
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
            ttl=settings.CACHE_TTL,
            model=RepositoryInfo,
            compute=compute,
            owner=owner,
            name=name,
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

        def compute(repo: BlobRepository) -> ReadmeContent:
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
            ttl=self._ttl_for_ref(ref),
            model=ReadmeContent,
            compute=compute,
            owner=owner,
            name=name,
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

        def compute(repo: BlobRepository) -> TagsPublic:
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
            ttl=settings.CACHE_TTL,
            model=TagsPublic,
            compute=compute,
            owner=owner,
            name=name,
        )

    async def activity_history(self, owner: str, name: str) -> GitActivityHistory:
        """Get cached, complete activity statistics for the repository's branches."""

        def compute(repo: BlobRepository) -> GitActivityHistory:
            _, _, default_branch = self._get_ref_counts(repo)
            return collect_git_activity(repo, default_branch)

        return await self._cached_model(
            key="activity-history:v1",
            ttl=settings.CACHE_TTL,
            model=GitActivityHistory,
            compute=compute,
            owner=owner,
            name=name,
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

        def compute(repo: BlobRepository) -> CommitsPublic:
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
            ttl=self._ttl_for_ref(ref),
            model=CommitsPublic,
            compute=compute,
            owner=owner,
            name=name,
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

        def compute(repo: BlobRepository) -> CommitDetail:
            store = repo.object_store
            try:
                obj = store[ObjectID(sha.encode())]
            except (KeyError, ValueError) as e:
                raise HTTPException(status_code=404, detail="Commit not found") from e
            if not isinstance(obj, Commit):
                raise HTTPException(status_code=404, detail="Commit not found")
            parent = store[obj.parents[0]] if obj.parents else None
            files = self._diff_files(store, parent.tree if isinstance(parent, Commit) else None, obj.tree, include_diff)
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
            ttl=settings.CACHE_IMMUTABLE_TTL,
            model=CommitDetail,
            compute=compute,
            owner=owner,
            name=name,
        )

    async def branch_heads(self, owner: str, name: str, base: str, head: str) -> tuple[str | None, str | None]:
        """Read two branch tips without opening packs, walking history, or calculating a diff."""
        return await self.storage.branch_heads(owner, name, base, head)

    async def compare_commits(
        self, owner: str, name: str, base_ref: str, head_ref: str, offset: int = 0, limit: int = 50
    ) -> CommitsPublic:
        """List only commits reachable from the head and absent from the base, with pagination."""

        def compute(repo: BlobRepository) -> CommitsPublic:
            base = self._try_resolve_ref(repo, base_ref)
            head = self._try_resolve_ref(repo, head_ref)
            if base is None or head is None:
                return CommitsPublic(data=[], count=0, ref=head_ref)

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

        return await self._cached_model(
            key=f"compare-commits:v1:{base_ref}:{head_ref}:{offset}:{limit}",
            ttl=settings.CACHE_TTL,
            model=CommitsPublic,
            compute=compute,
            owner=owner,
            name=name,
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

        def compute(repo: BlobRepository) -> CompareResult:
            base_sha = self._try_resolve_ref(repo, base_ref)
            head_sha = self._try_resolve_ref(repo, head_ref)
            if base_sha is None or head_sha is None:
                return CompareResult(files=[], additions=0, deletions=0)
            store = repo.object_store
            base_commit = store[ObjectID(base_sha)]
            head_commit = store[ObjectID(head_sha)]
            if not isinstance(base_commit, Commit) or not isinstance(head_commit, Commit):
                return CompareResult(files=[], additions=0, deletions=0)
            files = self._diff_files(store, base_commit.tree, head_commit.tree, include_diff)
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
            ttl=ttl,
            model=CompareResult,
            compute=compute,
            owner=owner,
            name=name,
        )

    async def get_diff_file(self, owner: str, name: str, head: str, file_path: str, base: str = "") -> CommitFileChange:
        """Return one highlighted file at immutable comparison revisions."""

        def compute(repo: BlobRepository) -> CommitFileChange:
            store = repo.object_store
            try:
                head_commit = store[ObjectID(head.encode())]
                base_commit = store[ObjectID(base.encode())] if base else None
            except (KeyError, ValueError) as error:
                raise HTTPException(status_code=404, detail="Comparison revision not found") from error
            if not isinstance(head_commit, Commit) or (
                base_commit is not None and (not isinstance(base_commit, Commit))
            ):
                raise HTTPException(status_code=404, detail="Comparison revision not found")
            old_tree = base_commit.tree if isinstance(base_commit, Commit) else None
            return self._diff_file(store, old_tree, head_commit.tree, file_path)

        return await self._cached_model(
            key=f"diff-file:v2:{base}:{head}:{file_path}",
            ttl=settings.CACHE_IMMUTABLE_TTL,
            model=CommitFileChange,
            compute=compute,
            owner=owner,
            name=name,
        )

    async def get_diff_context(
        self, owner: str, name: str, base: str, head: str, path: str, side: Literal["old", "new"], line: int
    ) -> DiffHunk:
        """Highlight and transfer only the bounded context needed for one legacy review comment."""

        def compute(repo: BlobRepository) -> DiffHunk:
            store = repo.object_store
            try:
                before, after = (store[ObjectID(base.encode())], store[ObjectID(head.encode())])
            except KeyError as error:
                raise HTTPException(status_code=404, detail="Comparison revision not found") from error
            if not isinstance(before, Commit) or not isinstance(after, Commit):
                raise HTTPException(status_code=404, detail="Comparison revision not found")
            file = self._diff_file(store, before.tree, after.tree, path, (side, line))
            if not file.hunks:
                raise HTTPException(status_code=404, detail="Diff context is unavailable for this line")
            return file.hunks[0]

        return await self._cached_model(
            key=f"review-context:v1:{base}:{head}:{path}:{side}:{line}",
            ttl=settings.CACHE_IMMUTABLE_TTL,
            model=DiffHunk,
            compute=compute,
            owner=owner,
            name=name,
        )

    async def load_repository(self, owner: str, name: str, *, fresh: bool = False) -> BlobRepository:
        """Load live storage or reuse the repository held by this request."""
        key = repo_key(owner, name)
        if not fresh and key in self.repositories:
            return self.repositories[key]
        names, refs = await self.storage.load(key)
        if not names and not refs:
            if await self.repository_store.find_by_owner_and_name(owner, name) is None:
                raise HTTPException(status_code=404, detail="Repository not found")
            repo = BlobRepository.create(self.storage.blob, f"{key}/packs/", cache=self.cache_client)
        else:
            repo = BlobRepository(self.storage.blob, f"{key}/packs/", names, cache=self.cache_client)
            repo.load_from_storage(refs)
        if not fresh:
            self.repositories[key] = repo
        return repo

    async def save_changes(self, owner: str, name: str) -> None:
        """Persist staged objects before refs, then invalidate cached responses."""
        repo = self.repositories.get(repo_key(owner, name))
        if repo is None:
            return
        changes = repo.get_pending_changes()
        if any(changes.values()):
            await self.storage.save(repo_key(owner, name), changes)
            repo.clear_pending_changes()
            await self.cache_client.invalidate(self._cache_group(owner, name))

    async def create_repository(self, owner: str, name: str) -> None:
        """Create and persist a bare repository's HEAD."""
        key = repo_key(owner, name)
        await self.storage.load(key)
        self.repositories[key] = BlobRepository.create(self.storage.blob, f"{key}/packs/", cache=self.cache_client)
        await self.save_changes(owner, name)

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
        if repo := self.repositories.pop(repo_key(target_owner, target_name), None):
            repo.close()

    async def delete_repository(self, owner: str, name: str) -> None:
        """Remove persisted objects, refs, and the request-local repository."""
        await self.storage.delete(repo_key(owner, name))
        await self.cache_client.invalidate(f"git:{repo_key(owner, name)}")
        if repo := self.repositories.pop(repo_key(owner, name), None):
            repo.close()

    def close(self) -> None:
        """Release request-local pack readers while retaining shared cached objects."""
        for repo in self.repositories.values():
            repo.close()
        self.repositories.clear()

    async def handle_http(self, request: GitHttpRequest) -> GitHttpResponse:
        """Run synchronous protocol processing off the event loop."""
        backend = DictBackend({f"/{key}": repo for key, repo in self.repositories.items()})
        return await run_in_threadpool(handle_http, backend, request)
