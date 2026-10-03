"""Repository management routes."""

from __future__ import annotations

import logging
import stat
import time
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Annotated, Protocol

from dulwich.objects import Blob, Commit, ObjectID, Tree
from dulwich.refs import SYMREF, Ref
from fastapi import APIRouter, HTTPException, Query
from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import TextLexer, get_lexer_for_filename
from pygments.util import ClassNotFound
from sqlalchemy import func as sa_func
from sqlalchemy import select

from app.api.dependencies import (
    BackendDep,
    BlobStorageClientDep,
    CurrentUser,
    RedisClientDep,
    RepositoryRepositoryDep,
    SessionDep,
)
from app.entities.issues import Issue
from app.entities.pull_requests import PullRequest
from app.entities.repositories import Repository as RepositoryEntity
from app.schemas.repositories import (
    BranchInfo,
    CommitInfo,
    CreateRepositoryRequest,
    FileContent,
    IssueCreate,
    IssuePublic,
    IssuesListPublic,
    IssueUpdate,
    PullRequestCreate,
    PullRequestPublic,
    PullRequestsListPublic,
    PullRequestUpdate,
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
    from app.clients.redis import AbstractRedisClient
    from app.clients.repositories import RepositoryRepository
    from app.entities.users import User
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


async def _load_repo(
    backend: BackendDep,
    blob_client: BlobStorageClientDep,
    redis_client: AbstractRedisClient,
    repo_path: str,
) -> BlobRepository:
    """Load a repository from storage.

    Args:
        backend: Git backend dependency.
        blob_client: Blob storage client dependency.
        redis_client: Redis client.
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

    packs, refs = await load_repository_from_storage(blob_client, redis_client, normalized)
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


async def get_repositories_from_redis(redis_client: AbstractRedisClient) -> list[Repository]:
    """Get list of repositories from Redis storage.

    Scans the Redis keys to find unique repository paths.

    Args:
        redis_client: Redis client.

    Returns:
        List of Repository objects.
    """
    # Keys are in format: repo_path/refs/ref_name
    repositories: dict[str, Repository] = {}

    keys = await redis_client.scan_keys("*/refs/*")

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
async def list_repositories(redis_client: RedisClientDep) -> RepositoriesPublic:
    """List all repositories.

    Returns a list of all Git repositories stored in the system.
    """
    repositories = await get_repositories_from_redis(redis_client)
    return RepositoriesPublic(data=repositories, count=len(repositories))


@router.post("/", status_code=201)
async def create_repository(
    body: CreateRepositoryRequest,
    backend: BackendDep,
    blob_client: BlobStorageClientDep,
    redis_client: RedisClientDep,
) -> Repository:
    """Create a new empty Git repository.

    Args:
        body: Repository creation request.
        backend: Git backend dependency.
        blob_client: Blob storage client dependency.
        redis_client: Redis client dependency.

    Returns:
        The created repository.
    """
    repo_path = f"{body.owner}/{body.name}.git"

    backend.create_repository(repo_path)

    # Save initial refs to storage (HEAD -> refs/heads/main)
    changes = backend.get_repository_changes(repo_path)
    if any(changes.values()):
        await save_repository_changes_to_storage(blob_client, redis_client, repo_path, changes)
        backend.clear_repository_changes(repo_path)

    return Repository(name=body.name, path=repo_path)


@router.get("/{path:path}/tree")
async def get_tree(
    path: str,
    ref: str = "main",
    tree_path: str = "",
    *,
    backend: BackendDep,
    blob_client: BlobStorageClientDep,
    redis_client: RedisClientDep,
) -> TreeListing:
    """Get directory listing for a repository path.

    Args:
        path: Repository path (e.g., "user/repo" or "user/repo.git").
        ref: Git ref to browse (default: "main").
        tree_path: Subdirectory path within the repo.
        backend: Git backend dependency.
        blob_client: Blob storage client dependency.
        redis_client: Redis client dependency.

    Returns:
        TreeListing with directory entries.
    """
    repo = await _load_repo(backend, blob_client, redis_client, path)
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
    path: str,
    ref: str = "main",
    file_path: str = "",
    *,
    backend: BackendDep,
    blob_client: BlobStorageClientDep,
    redis_client: RedisClientDep,
) -> FileContent:
    """Get file content with syntax highlighting.

    Args:
        path: Repository path (e.g., "user/repo" or "user/repo.git").
        ref: Git ref (default: "main").
        file_path: File path within the repository.
        backend: Git backend dependency.
        blob_client: Blob storage client dependency.
        redis_client: Redis client dependency.

    Returns:
        FileContent with highlighted HTML and CSS.
    """
    if not file_path:
        raise HTTPException(status_code=400, detail="file_path is required")

    repo = await _load_repo(backend, blob_client, redis_client, path)
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


def _get_ref_counts(repo: BlobRepository) -> tuple[int, int, str]:
    """Count branches and tags, and determine default branch.

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


def _get_commit_info(repo: BlobRepository, commit_sha: bytes) -> CommitInfo:
    """Extract commit information from a commit SHA.

    Args:
        repo: The repository.
        commit_sha: The commit SHA.

    Returns:
        CommitInfo with commit details.
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

    return CommitInfo(
        sha=sha_str[:10],
        message=message,
        author=author,
        timestamp=timestamp,
    )


def _find_readme_in_tree(repo: BlobRepository, tree: Tree) -> tuple[str, str] | None:
    """Find and read a README file in a tree.

    Args:
        repo: The repository.
        tree: The tree to search.

    Returns:
        Tuple of (filename, content) or None if no README found.
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


@router.get("/{path:path}/info")
async def get_repository_info(
    path: str,
    *,
    backend: BackendDep,
    blob_client: BlobStorageClientDep,
    redis_client: RedisClientDep,
    ref: str = "main",
) -> RepositoryInfo:
    """Get extended repository information.

    Includes branch/tag counts, default branch, and last commit info.

    Args:
        path: Repository path (e.g., "user/repo" or "user/repo.git").
        backend: Git backend dependency.
        blob_client: Blob storage dependency.
        redis_client: Redis client dependency.
        ref: Git ref (default: "main").

    Returns:
        RepositoryInfo with metadata.
    """
    repo = await _load_repo(backend, blob_client, redis_client, path)

    branch_count, tag_count, default_branch = _get_ref_counts(repo)

    normalized = path.strip("/")
    name = normalized.rstrip("/").split("/")[-1]
    if name.endswith(".git"):
        name = name[:-4]

    last_commit = None
    try:
        commit_sha = _resolve_ref(repo, ref)
        last_commit = _get_commit_info(repo, commit_sha)
    except HTTPException:
        pass

    return RepositoryInfo(
        name=name,
        path=normalized if normalized.endswith(".git") else f"{normalized}.git",
        default_branch=default_branch,
        branch_count=branch_count,
        tag_count=tag_count,
        last_commit=last_commit,
    )


@router.get("/{path:path}/readme")
async def get_readme(
    path: str,
    *,
    backend: BackendDep,
    blob_client: BlobStorageClientDep,
    redis_client: RedisClientDep,
    ref: str = "main",
    tree_path: str = "",
) -> ReadmeContent:
    """Get README content from a repository directory.

    Searches for common README filenames in the specified directory.

    Args:
        path: Repository path (e.g., "user/repo" or "user/repo.git").
        backend: Git backend dependency.
        blob_client: Blob storage dependency.
        redis_client: Redis client dependency.
        ref: Git ref (default: "main").
        tree_path: Subdirectory path within the repo.

    Returns:
        ReadmeContent with filename and raw content.

    Raises:
        HTTPException: 404 if no README found.
    """
    repo = await _load_repo(backend, blob_client, redis_client, path)
    commit_sha = _resolve_ref(repo, ref)
    tree = _get_tree_at_path(repo, commit_sha, tree_path)

    result = _find_readme_in_tree(repo, tree)
    if result is None:
        raise HTTPException(status_code=404, detail="README not found")

    filename, content = result
    html = render_markdown(content) if filename.lower().endswith((".md", ".markdown")) else ""
    return ReadmeContent(filename=filename, content=content, html=html)


@router.get("/{path:path}/branches")
async def list_branches(
    path: str,
    *,
    backend: BackendDep,
    blob_client: BlobStorageClientDep,
    redis_client: RedisClientDep,
) -> list[BranchInfo]:
    """List all branches in a repository.

    Args:
        path: Repository path (e.g., "user/repo" or "user/repo.git").
        backend: Git backend dependency.
        blob_client: Blob storage dependency.
        redis_client: Redis client dependency.

    Returns:
        List of BranchInfo with branch names and default flag.
    """
    repo = await _load_repo(backend, blob_client, redis_client, path)
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


def _normalize_repo_path(path: str) -> str:
    """Normalize repository path to include .git suffix.

    Args:
        path: Repository path (e.g., "user/repo" or "user/repo.git").

    Returns:
        Normalized path with .git suffix.
    """
    normalized = path.strip("/")
    if not normalized.endswith(".git"):
        normalized = normalized + ".git"
    return normalized


def _ensure_repository(
    repository_store: RepositoryRepository,
    repo_path: str,
    current_user: User,
) -> RepositoryEntity:
    """Get an existing repository row or create one for the given path.

    Args:
        repository_store: Repository store dependency.
        repo_path: Normalized repository path (e.g., "user/repo.git").
        current_user: The authenticated user.

    Returns:
        The repository entity.
    """
    repository = repository_store.get_by_path(repo_path)
    if repository is None:
        name = repo_path.rstrip("/").split("/")[-1]
        if name.endswith(".git"):
            name = name[:-4]
        repository = RepositoryEntity(name=name, path=repo_path, owner_id=current_user.id)
        repository_store.add(repository)
    return repository


def _issue_to_public(issue: Issue, repo_path: str) -> IssuePublic:
    """Convert an issue entity to its public representation.

    Args:
        issue: The issue entity.
        repo_path: The repository path.

    Returns:
        The public issue representation.
    """
    return IssuePublic(
        id=issue.id,
        repo_path=repo_path,
        number=issue.number,
        title=issue.title,
        body=issue.body,
        state=issue.state,
        author_email=issue.author_email,
        created_at=issue.created_at,
        updated_at=issue.updated_at,
    )


def _pull_request_to_public(pr: PullRequest, repo_path: str) -> PullRequestPublic:
    """Convert a pull request entity to its public representation.

    Args:
        pr: The pull request entity.
        repo_path: The repository path.

    Returns:
        The public pull request representation.
    """
    return PullRequestPublic(
        id=pr.id,
        repo_path=repo_path,
        number=pr.number,
        title=pr.title,
        body=pr.body,
        state=pr.state,
        head_branch=pr.head_branch,
        base_branch=pr.base_branch,
        author_email=pr.author_email,
        merge_base=pr.merge_base,
        merged_commit_id=pr.merged_commit_id,
        has_merged=pr.has_merged,
        created_at=pr.created_at,
        updated_at=pr.updated_at,
    )


@router.get("/{path:path}/issues")
async def list_issues(
    path: str,
    session: SessionDep,
    repository_store: RepositoryRepositoryDep,
    state: Annotated[str, Query(description="Filter by state: open, closed, or all")] = "all",
) -> IssuesListPublic:
    """List issues for a repository.

    Args:
        path: Repository path (e.g., "user/repo").
        session: Database session.
        repository_store: Repository store dependency.
        state: Filter by state (open, closed, all).

    Returns:
        IssuesListPublic with issues and counts.
    """
    repo_path = _normalize_repo_path(path)
    repository = repository_store.get_by_path(repo_path)
    if repository is None:
        return IssuesListPublic(data=[], count=0, open_count=0, closed_count=0)

    stmt = select(Issue).where(Issue.repo_id == repository.id)
    if state in ("open", "closed"):
        stmt = stmt.where(Issue.state == state)
    stmt = stmt.order_by(Issue.number.desc())

    issues = list(session.execute(stmt).scalars().all())

    open_count = session.execute(
        select(sa_func.count()).select_from(Issue).where(Issue.repo_id == repository.id, Issue.state == "open")
    ).scalar_one()
    closed_count = session.execute(
        select(sa_func.count()).select_from(Issue).where(Issue.repo_id == repository.id, Issue.state == "closed")
    ).scalar_one()

    return IssuesListPublic(
        data=[_issue_to_public(issue, repo_path) for issue in issues],
        count=len(issues),
        open_count=open_count,
        closed_count=closed_count,
    )


@router.post("/{path:path}/issues", status_code=201)
async def create_issue(
    path: str,
    body: IssueCreate,
    session: SessionDep,
    repository_store: RepositoryRepositoryDep,
    current_user: CurrentUser,
) -> IssuePublic:
    """Create a new issue.

    Args:
        path: Repository path (e.g., "user/repo").
        body: Issue creation data.
        session: Database session.
        repository_store: Repository store dependency.
        current_user: The authenticated user.

    Returns:
        The created issue.
    """
    repo_path = _normalize_repo_path(path)
    repository = _ensure_repository(repository_store, repo_path, current_user)

    max_number = session.execute(select(sa_func.max(Issue.number)).where(Issue.repo_id == repository.id)).scalar_one()
    next_number = (max_number or 0) + 1

    issue = Issue(
        repo_id=repository.id,
        number=next_number,
        title=body.title,
        body=body.body,
        state="open",
        author_email=current_user.email,
    )
    session.add(issue)
    session.commit()
    session.refresh(issue)

    return _issue_to_public(issue, repo_path)


@router.get("/{path:path}/issues/{number}")
async def get_issue(
    path: str,
    number: int,
    session: SessionDep,
    repository_store: RepositoryRepositoryDep,
) -> IssuePublic:
    """Get a single issue by number.

    Args:
        path: Repository path.
        number: Issue number.
        session: Database session.
        repository_store: Repository store dependency.

    Returns:
        The issue.

    Raises:
        HTTPException: If issue not found.
    """
    repo_path = _normalize_repo_path(path)
    repository = repository_store.get_by_path(repo_path)
    if repository is None:
        raise HTTPException(status_code=404, detail="Issue not found")

    issue = session.execute(
        select(Issue).where(Issue.repo_id == repository.id, Issue.number == number)
    ).scalar_one_or_none()
    if issue is None:
        raise HTTPException(status_code=404, detail="Issue not found")

    return _issue_to_public(issue, repo_path)


@router.patch("/{path:path}/issues/{number}")
async def update_issue(
    path: str,
    number: int,
    body: IssueUpdate,
    session: SessionDep,
    repository_store: RepositoryRepositoryDep,
) -> IssuePublic:
    """Update an issue.

    Args:
        path: Repository path.
        number: Issue number.
        body: Fields to update.
        session: Database session.
        repository_store: Repository store dependency.

    Returns:
        The updated issue.

    Raises:
        HTTPException: If issue not found.
    """
    repo_path = _normalize_repo_path(path)
    repository = repository_store.get_by_path(repo_path)
    if repository is None:
        raise HTTPException(status_code=404, detail="Issue not found")

    issue = session.execute(
        select(Issue).where(Issue.repo_id == repository.id, Issue.number == number)
    ).scalar_one_or_none()
    if issue is None:
        raise HTTPException(status_code=404, detail="Issue not found")

    if body.title is not None:
        issue.title = body.title
    if body.body is not None:
        issue.body = body.body
    if body.state is not None:
        if body.state not in ("open", "closed"):
            raise HTTPException(status_code=400, detail="State must be 'open' or 'closed'")
        issue.state = body.state

    issue.updated_at = datetime.now(UTC)
    session.commit()
    session.refresh(issue)

    return _issue_to_public(issue, repo_path)


@router.get("/{path:path}/pulls")
async def list_pull_requests(
    path: str,
    session: SessionDep,
    repository_store: RepositoryRepositoryDep,
    state: Annotated[str, Query(description="Filter by state: open, closed, merged, or all")] = "all",
) -> PullRequestsListPublic:
    """List pull requests for a repository.

    Args:
        path: Repository path (e.g., "user/repo").
        session: Database session.
        repository_store: Repository store dependency.
        state: Filter by state (open, closed, merged, all).

    Returns:
        PullRequestsListPublic with PRs and counts.
    """
    repo_path = _normalize_repo_path(path)
    repository = repository_store.get_by_path(repo_path)
    if repository is None:
        return PullRequestsListPublic(data=[], count=0, open_count=0, closed_count=0)

    stmt = select(PullRequest).where(PullRequest.repo_id == repository.id)
    if state in ("open", "closed", "merged"):
        stmt = stmt.where(PullRequest.state == state)
    stmt = stmt.order_by(PullRequest.number.desc())

    prs = list(session.execute(stmt).scalars().all())

    open_count = session.execute(
        select(sa_func.count())
        .select_from(PullRequest)
        .where(PullRequest.repo_id == repository.id, PullRequest.state == "open")
    ).scalar_one()
    closed_count = session.execute(
        select(sa_func.count())
        .select_from(PullRequest)
        .where(PullRequest.repo_id == repository.id, PullRequest.state.in_(["closed", "merged"]))
    ).scalar_one()

    return PullRequestsListPublic(
        data=[_pull_request_to_public(pr, repo_path) for pr in prs],
        count=len(prs),
        open_count=open_count,
        closed_count=closed_count,
    )


@router.post("/{path:path}/pulls", status_code=201)
async def create_pull_request(
    path: str,
    body: PullRequestCreate,
    session: SessionDep,
    repository_store: RepositoryRepositoryDep,
    current_user: CurrentUser,
) -> PullRequestPublic:
    """Create a new pull request.

    Args:
        path: Repository path (e.g., "user/repo").
        body: Pull request creation data.
        session: Database session.
        repository_store: Repository store dependency.
        current_user: The authenticated user.

    Returns:
        The created pull request.
    """
    repo_path = _normalize_repo_path(path)
    repository = _ensure_repository(repository_store, repo_path, current_user)

    max_number = session.execute(
        select(sa_func.max(PullRequest.number)).where(PullRequest.repo_id == repository.id)
    ).scalar_one()
    next_number = (max_number or 0) + 1

    pr = PullRequest(
        repo_id=repository.id,
        number=next_number,
        title=body.title,
        body=body.body,
        state="open",
        author_email=current_user.email,
        head_repo_id=repository.id,
        base_repo_id=repository.id,
        head_branch=body.head_branch,
        base_branch=body.base_branch,
    )
    session.add(pr)
    session.commit()
    session.refresh(pr)

    return _pull_request_to_public(pr, repo_path)


@router.get("/{path:path}/pulls/{number}")
async def get_pull_request(
    path: str,
    number: int,
    session: SessionDep,
    repository_store: RepositoryRepositoryDep,
) -> PullRequestPublic:
    """Get a single pull request by number.

    Args:
        path: Repository path.
        number: Pull request number.
        session: Database session.
        repository_store: Repository store dependency.

    Returns:
        The pull request.

    Raises:
        HTTPException: If pull request not found.
    """
    repo_path = _normalize_repo_path(path)
    repository = repository_store.get_by_path(repo_path)
    if repository is None:
        raise HTTPException(status_code=404, detail="Pull request not found")

    pr = session.execute(
        select(PullRequest).where(PullRequest.repo_id == repository.id, PullRequest.number == number)
    ).scalar_one_or_none()
    if pr is None:
        raise HTTPException(status_code=404, detail="Pull request not found")

    return _pull_request_to_public(pr, repo_path)


@router.patch("/{path:path}/pulls/{number}")
async def update_pull_request(
    path: str,
    number: int,
    body: PullRequestUpdate,
    session: SessionDep,
    repository_store: RepositoryRepositoryDep,
) -> PullRequestPublic:
    """Update a pull request.

    Args:
        path: Repository path.
        number: Pull request number.
        body: Fields to update.
        session: Database session.
        repository_store: Repository store dependency.

    Returns:
        The updated pull request.

    Raises:
        HTTPException: If pull request not found.
    """
    repo_path = _normalize_repo_path(path)
    repository = repository_store.get_by_path(repo_path)
    if repository is None:
        raise HTTPException(status_code=404, detail="Pull request not found")

    pr = session.execute(
        select(PullRequest).where(PullRequest.repo_id == repository.id, PullRequest.number == number)
    ).scalar_one_or_none()
    if pr is None:
        raise HTTPException(status_code=404, detail="Pull request not found")

    if body.title is not None:
        pr.title = body.title
    if body.body is not None:
        pr.body = body.body
    if body.state is not None:
        if body.state not in ("open", "closed", "merged"):
            raise HTTPException(status_code=400, detail="State must be 'open', 'closed', or 'merged'")
        pr.state = body.state

    pr.updated_at = datetime.now(UTC)
    session.commit()
    session.refresh(pr)

    return _pull_request_to_public(pr, repo_path)


@router.get("/{path:path}")
async def get_repository(path: str, redis_client: RedisClientDep) -> Repository:
    """Get a specific repository by path."""
    repositories = await get_repositories_from_redis(redis_client)
    for repo in repositories:
        if repo.path in (path, f"{path}.git"):
            return repo
    raise HTTPException(status_code=404, detail="Repository not found")
