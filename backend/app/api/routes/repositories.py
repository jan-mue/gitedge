"""Repository management routes."""

from __future__ import annotations

import logging
import stat
from typing import TYPE_CHECKING, Protocol

from dulwich.objects import Blob, Commit, ObjectID, Tree
from dulwich.refs import SYMREF, Ref
from fastapi import APIRouter, HTTPException
from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import TextLexer, get_lexer_for_filename
from pygments.util import ClassNotFound

from app.api.dependencies import BackendDep, BlobStorageClientDep
from app.clients.redis import redis_scan_keys
from app.schemas.repositories import (
    CreateRepositoryRequest,
    FileContent,
    RepositoriesPublic,
    Repository,
    TreeEntry,
    TreeListing,
)
from app.services.blob_backend import load_repository_from_storage, save_repository_changes_to_storage

if TYPE_CHECKING:
    from app.services.blob_repository import BlobRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/repositories", tags=["repositories"])


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


async def _load_repo(backend: BackendDep, blob_client: BlobStorageClientDep, repo_path: str) -> BlobRepository:
    """Load a repository from storage.

    Args:
        backend: Git backend dependency.
        blob_client: Blob storage client dependency.
        repo_path: Repository path (e.g., "user/repo.git").

    Returns:
        Loaded BlobRepository instance.

    Raises:
        HTTPException: If repository not found.
    """
    normalized = repo_path.strip("/")
    if not normalized.endswith(".git"):
        normalized = normalized + ".git"

    logger.debug("Loading repository: raw=%s, normalized=%s", repo_path, normalized)

    if backend.repository_exists(normalized):
        logger.debug("Repository found in cache: %s", normalized)
        return backend.open_repository(normalized)

    packs, refs = await load_repository_from_storage(blob_client, normalized)
    logger.debug("Loaded from storage: %s (packs=%d, refs=%d)", normalized, len(packs), len(refs))
    if not packs and not refs:
        raise HTTPException(status_code=404, detail="Repository not found")
    return backend.load_repository_from_data(normalized, packs, refs)


def _resolve_ref(repo: BlobRepository, ref_name: str) -> bytes:
    """Resolve a ref name to a commit SHA.

    Args:
        repo: The repository.
        ref_name: Ref name (e.g., "main", "refs/heads/main").

    Returns:
        The commit SHA as bytes.

    Raises:
        HTTPException: If ref not found.
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

    raise HTTPException(status_code=404, detail=f"Ref '{ref_name}' not found")


def _get_tree_at_path(repo: BlobRepository, commit_sha: bytes, path: str) -> Tree:
    """Walk a commit's tree to a specific subdirectory.

    Args:
        repo: The repository.
        commit_sha: The commit SHA.
        path: Path within the repository (e.g., "src/app").

    Returns:
        The Tree object at the given path.

    Raises:
        HTTPException: If path not found or not a tree.
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


def _get_blob_at_path(repo: BlobRepository, commit_sha: bytes, path: str) -> tuple[Blob, str]:
    """Get a file blob at a specific path.

    Args:
        repo: The repository.
        commit_sha: The commit SHA.
        path: File path within the repository.

    Returns:
        Tuple of (Blob object, filename).

    Raises:
        HTTPException: If file not found or not a blob.
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


async def get_repositories_from_redis() -> list[Repository]:
    """Get list of repositories from Redis storage.

    Scans the Redis keys to find unique repository paths.

    Returns:
        List of Repository objects.
    """
    # Keys are in format: repo_path/refs/ref_name
    repositories: dict[str, Repository] = {}

    keys = await redis_scan_keys("*/refs/*")

    for key_name in keys:
        if "/refs/" in key_name:
            repo_path = key_name.split("/refs/")[0]
            if repo_path not in repositories:
                name = repo_path.rstrip("/").split("/")[-1]
                if name.endswith(".git"):
                    name = name[:-4]
                repositories[repo_path] = Repository(name=name, path=repo_path)

    return list(repositories.values())


@router.get("/")
async def list_repositories() -> RepositoriesPublic:
    """List all repositories.

    Returns a list of all Git repositories stored in the system.
    """
    repositories = await get_repositories_from_redis()
    return RepositoriesPublic(data=repositories, count=len(repositories))


@router.post("/", status_code=201)
async def create_repository(
    body: CreateRepositoryRequest,
    backend: BackendDep,
    blob_client: BlobStorageClientDep,
) -> Repository:
    """Create a new empty Git repository.

    Args:
        body: Repository creation request.
        backend: Git backend dependency.
        blob_client: Blob storage client dependency.

    Returns:
        The created repository.
    """
    repo_path = f"{body.owner}/{body.name}.git"

    backend.create_repository(repo_path)

    # Save initial refs to storage (HEAD -> refs/heads/main)
    changes = backend.get_repository_changes(repo_path)
    if any(changes.values()):
        await save_repository_changes_to_storage(blob_client, repo_path, changes)
        backend.clear_repository_changes(repo_path)

    return Repository(name=body.name, path=repo_path)


@router.get("/{path:path}/tree")
async def get_tree(
    backend: BackendDep,
    blob_client: BlobStorageClientDep,
    path: str,
    ref: str = "main",
    tree_path: str = "",
) -> TreeListing:
    """Get directory listing for a repository path.

    Args:
        backend: Git backend dependency.
        blob_client: Blob storage client dependency.
        path: Repository path (e.g., "user/repo" or "user/repo.git").
        ref: Git ref to browse (default: "main").
        tree_path: Subdirectory path within the repo.

    Returns:
        TreeListing with directory entries.
    """
    repo = await _load_repo(backend, blob_client, path)
    commit_sha = _resolve_ref(repo, ref)
    tree = _get_tree_at_path(repo, commit_sha, tree_path)

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

    return TreeListing(
        entries=entries,
        repo_path=path,
        tree_path=tree_path,
        ref=ref,
    )


@router.get("/{path:path}/blob")
async def get_blob(
    backend: BackendDep,
    blob_client: BlobStorageClientDep,
    path: str,
    ref: str = "main",
    file_path: str = "",
) -> FileContent:
    """Get file content with syntax highlighting.

    Args:
        backend: Git backend dependency.
        blob_client: Blob storage client dependency.
        path: Repository path (e.g., "user/repo" or "user/repo.git").
        ref: Git ref (default: "main").
        file_path: File path within the repository.

    Returns:
        FileContent with highlighted HTML and CSS.
    """
    if not file_path:
        raise HTTPException(status_code=400, detail="file_path is required")

    repo = await _load_repo(backend, blob_client, path)
    commit_sha = _resolve_ref(repo, ref)
    blob, filename = _get_blob_at_path(repo, commit_sha, file_path)

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


@router.get("/{path:path}")
async def get_repository(path: str) -> Repository:
    """Get a specific repository by path."""
    repositories = await get_repositories_from_redis()
    for repo in repositories:
        if repo.path in (path, f"{path}.git"):
            return repo
    raise HTTPException(status_code=404, detail="Repository not found")
