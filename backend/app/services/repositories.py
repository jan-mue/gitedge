"""Service for browsing and managing Git repositories."""

from __future__ import annotations

import logging
import stat
import time
from typing import TYPE_CHECKING, Protocol

from dulwich.objects import Blob, Commit, ObjectID, Tree
from dulwich.refs import SYMREF, Ref
from fastapi import HTTPException
from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import TextLexer, get_lexer_for_filename
from pygments.util import ClassNotFound

from app.entities.repositories import Repository as RepositoryEntity
from app.schemas.repositories import (
    BranchInfo,
    CommitInfo,
    FileContent,
    ReadmeContent,
    RepositoriesPublic,
    Repository,
    RepositoryInfo,
    TreeEntry,
    TreeListing,
)
from app.services.blob_backend import load_repository_from_storage, save_repository_changes_to_storage
from app.services.markdown import render_markdown

if TYPE_CHECKING:
    from app.clients.blob_storage import BlobStorageClient
    from app.clients.redis import AbstractRedisClient
    from app.clients.repositories import RepositoryStore
    from app.entities.users import User
    from app.services.blob_backend import BlobBackend
    from app.services.blob_repository import BlobRepository

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


def normalize_repo_path(path: str) -> str:
    """Normalize a repository path to include the .git suffix.

    Args:
        path: Repository path (e.g., "user/repo" or "user/repo.git").

    Returns:
        Normalized path with .git suffix.
    """
    normalized = path.strip("/")
    if not normalized.endswith(".git"):
        normalized = normalized + ".git"
    return normalized


def repository_name_from_path(path: str) -> str:
    """Derive the repository name from its path.

    Args:
        path: Repository path (e.g., "user/repo" or "user/repo.git").

    Returns:
        The repository name without the .git suffix.
    """
    name = normalize_repo_path(path).rstrip("/").split("/")[-1]
    return name[:-4] if name.endswith(".git") else name


def ensure_repository(store: RepositoryStore, path: str, user: User) -> RepositoryEntity:
    """Get an existing repository row or create one for the given path.

    Args:
        store: Repository store.
        path: Repository path (e.g., "user/repo").
        user: The authenticated user.

    Returns:
        The repository entity.
    """
    repo_path = normalize_repo_path(path)
    repository = store.get_by_path(repo_path)
    if repository is None:
        repository = RepositoryEntity(name=repository_name_from_path(repo_path), path=repo_path, owner_id=user.id)
        store.add(repository)
    return repository


class RepositoryService:
    """Service for browsing and managing Git repositories."""

    def __init__(
        self,
        backend: BlobBackend,
        blob_client: BlobStorageClient,
        redis_client: AbstractRedisClient,
    ) -> None:
        """Initialize the repository service.

        Args:
            backend: Git backend.
            blob_client: Blob storage client.
            redis_client: Redis client.
        """
        self.backend = backend
        self.blob_client = blob_client
        self.redis_client = redis_client

    async def list_repositories(self) -> RepositoriesPublic:
        """List all repositories.

        Scans Redis keys to find unique repository paths.

        Returns:
            RepositoriesPublic with the discovered repositories.
        """
        repositories: dict[str, Repository] = {}

        keys = await self.redis_client.scan_keys("*/refs/*")
        for key_name in keys:
            if "/refs/" in key_name:
                repo_path = key_name.split("/refs/")[0]
                if repo_path not in repositories:
                    repositories[repo_path] = Repository(name=repository_name_from_path(repo_path), path=repo_path)

        data = list(repositories.values())
        return RepositoriesPublic(data=data, count=len(data))

    async def get_repository(self, path: str) -> Repository:
        """Get a specific repository by path.

        Args:
            path: Repository path.

        Returns:
            The repository.

        Raises:
            HTTPException: If the repository does not exist.
        """
        normalized = normalize_repo_path(path)
        repositories = (await self.list_repositories()).data
        for repository in repositories:
            if repository.path == normalized:
                return repository
        raise HTTPException(status_code=404, detail="Repository not found")

    async def create_repository(self, owner: str, name: str) -> Repository:
        """Create a new empty Git repository.

        Args:
            owner: Repository owner.
            name: Repository name.

        Returns:
            The created repository.
        """
        repo_path = f"{owner}/{name}.git"

        self.backend.create_repository(repo_path)

        changes = self.backend.get_repository_changes(repo_path)
        if any(changes.values()):
            await save_repository_changes_to_storage(self.blob_client, self.redis_client, repo_path, changes)
            self.backend.clear_repository_changes(repo_path)

        return Repository(name=name, path=repo_path)

    async def ensure_loaded(self, path: str) -> None:
        """Ensure a repository is loaded into the backend, creating it if absent.

        Args:
            path: Repository path.
        """
        normalized = normalize_repo_path(path)
        if self.backend.repository_exists(normalized):
            return

        packs, refs = await load_repository_from_storage(self.blob_client, self.redis_client, normalized)
        if packs or refs:
            self.backend.load_repository_from_data(normalized, packs, refs)
        else:
            self.backend.create_repository(normalized)

    async def save_changes(self, path: str) -> None:
        """Persist pending repository changes to storage.

        Args:
            path: Repository path.
        """
        normalized = normalize_repo_path(path)
        changes = self.backend.get_repository_changes(normalized)
        if not any(changes.values()):
            return

        await save_repository_changes_to_storage(self.blob_client, self.redis_client, normalized, changes)
        self.backend.clear_repository_changes(normalized)

    async def load_repository(self, path: str) -> BlobRepository:
        """Load a repository from storage.

        Args:
            path: Repository path (e.g., "user/repo.git").

        Returns:
            The loaded repository.

        Raises:
            HTTPException: If the repository does not exist.
        """
        normalized = normalize_repo_path(path)
        logger.debug("Loading repository: raw=%s, normalized=%s", path, normalized)

        if self.backend.repository_exists(normalized):
            logger.debug("Repository found in cache: %s", normalized)
            return self.backend.open_repository(normalized)

        packs, refs = await load_repository_from_storage(self.blob_client, self.redis_client, normalized)
        logger.debug("Loaded from storage: %s (packs=%d, refs=%d)", normalized, len(packs), len(refs))
        if not packs and not refs:
            raise HTTPException(status_code=404, detail="Repository not found")
        return self.backend.load_repository_from_data(normalized, packs, refs)

    async def get_tree(self, path: str, ref: str, tree_path: str) -> TreeListing:
        """Get the directory listing for a repository path.

        Args:
            path: Repository path.
            ref: Git ref to browse.
            tree_path: Subdirectory path within the repository.

        Returns:
            TreeListing with the directory entries.
        """
        repo = await self.load_repository(path)
        commit_sha = self._resolve_ref(repo, ref)
        tree = self._get_tree_at_path(repo, commit_sha, tree_path)

        entries: list[TreeEntry] = []
        store = repo.object_store

        for item in sorted(tree.items(), key=lambda e: (not stat.S_ISDIR(e.mode), e.path)):
            name = item.path.decode()
            entry_path = f"{tree_path}/{name}".lstrip("/") if tree_path else name
            is_dir = stat.S_ISDIR(item.mode)

            size = None
            if not is_dir:
                obj = store[item.sha]
                if isinstance(obj, Blob):
                    size = len(obj.data)

            entries.append(
                TreeEntry(
                    name=name,
                    path=entry_path,
                    type="tree" if is_dir else "blob",
                    size=size,
                )
            )

        return TreeListing(entries=entries, repo_path=path, tree_path=tree_path, ref=ref)

    async def get_blob(self, path: str, ref: str, file_path: str) -> FileContent:
        """Get file content with syntax highlighting.

        Args:
            path: Repository path.
            ref: Git ref.
            file_path: File path within the repository.

        Returns:
            FileContent with highlighted HTML and CSS.

        Raises:
            HTTPException: If file_path is empty.
        """
        if not file_path:
            raise HTTPException(status_code=400, detail="file_path is required")

        repo = await self.load_repository(path)
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

        highlighted_html = highlight(content, lexer, formatter)
        css = _get_style_defs(formatter, ".highlight")

        # Scope all dark CSS rules under .dark to prevent them from leaking into
        # light mode. get_style_defs() only prefixes .highlight rules, but Pygments
        # also emits global rules (td.linenos, span.linenos, pre) that need scoping.
        raw_dark_css = _get_style_defs(dark_formatter, ".highlight")
        css_dark = "\n".join(
            f".dark {line}" if line and not line.startswith(".dark") else line for line in raw_dark_css.split("\n")
        )
        line_count = content.count("\n") + (1 if content and not content.endswith("\n") else 0)

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
        )

    async def get_info(self, path: str, ref: str) -> RepositoryInfo:
        """Get extended repository information.

        Includes branch/tag counts, default branch, and last commit info.

        Args:
            path: Repository path.
            ref: Git ref.

        Returns:
            RepositoryInfo with metadata.
        """
        repo = await self.load_repository(path)

        branch_count, tag_count, default_branch = self._get_ref_counts(repo)

        normalized = path.strip("/")
        name = repository_name_from_path(normalized)

        commit_sha = self._try_resolve_ref(repo, ref)
        last_commit = self._get_commit_info(repo, commit_sha) if commit_sha is not None else None

        return RepositoryInfo(
            name=name,
            path=normalize_repo_path(normalized),
            default_branch=default_branch,
            branch_count=branch_count,
            tag_count=tag_count,
            last_commit=last_commit,
        )

    async def get_readme(self, path: str, ref: str, tree_path: str) -> ReadmeContent:
        """Get README content from a repository directory.

        Args:
            path: Repository path.
            ref: Git ref.
            tree_path: Subdirectory path within the repository.

        Returns:
            ReadmeContent with the filename, raw content and rendered HTML.

        Raises:
            HTTPException: If no README is found.
        """
        repo = await self.load_repository(path)
        commit_sha = self._resolve_ref(repo, ref)
        tree = self._get_tree_at_path(repo, commit_sha, tree_path)

        result = self._find_readme_in_tree(repo, tree)
        if result is None:
            raise HTTPException(status_code=404, detail="README not found")

        filename, content = result
        html = render_markdown(content) if filename.lower().endswith((".md", ".markdown")) else ""
        return ReadmeContent(filename=filename, content=content, html=html)

    async def list_branches(self, path: str) -> list[BranchInfo]:
        """List all branches in a repository.

        Args:
            path: Repository path.

        Returns:
            List of BranchInfo with branch names and default flag.
        """
        repo = await self.load_repository(path)
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

        return branches

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
        sha = RepositoryService._try_resolve_ref(repo, ref_name)
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

        return CommitInfo(sha=sha_str[:10], message=message, author=author, timestamp=timestamp)

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
            name = item.path.decode()
            if name in _README_NAMES and not stat.S_ISDIR(item.mode):
                obj = store[item.sha]
                if isinstance(obj, Blob):
                    try:
                        content = obj.data.decode("utf-8")
                    except UnicodeDecodeError:
                        content = "(binary file)"
                    return name, content

        return None
