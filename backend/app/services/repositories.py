"""Service for browsing and managing Git repositories."""

from __future__ import annotations

import io
import logging
import re
import stat
import time
from typing import TYPE_CHECKING, Protocol

from dulwich.objects import Blob, Commit, ObjectID, Tag, Tree
from dulwich.patch import write_commit_diff, write_tree_diff
from dulwich.refs import SYMREF, Ref
from fastapi import HTTPException
from pydantic import BaseModel, TypeAdapter
from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import TextLexer, get_lexer_for_filename
from pygments.util import ClassNotFound

from app.config import settings
from app.entities.repositories import Repository as RepositoryEntity
from app.schemas.releases import TagInfo, TagsPublic
from app.schemas.repositories import (
    BranchInfo,
    CommitChangeType,
    CommitDetail,
    CommitFileChange,
    CommitInfo,
    CommitListItem,
    CommitsPublic,
    CompareResult,
    FileContent,
    ReadmeContent,
    RepositoriesPublic,
    Repository,
    RepositoryInfo,
    TreeEntry,
    TreeEntryType,
    TreeListing,
)
from app.services.blob_backend import load_repository_from_storage, save_repository_changes_to_storage
from app.services.markdown import render_markdown
from app.utils.cache_headers import (
    CACHE_CONTROL_IMMUTABLE,
    CACHE_CONTROL_PRIVATE,
    CACHE_CONTROL_REVALIDATE,
    is_commit_sha,
)

if TYPE_CHECKING:
    import uuid
    from collections.abc import Awaitable, Callable

    from app.clients.blob_storage import BlobStorageClient
    from app.clients.cache import AbstractCacheClient
    from app.clients.redis import AbstractRedisClient
    from app.clients.repositories import RepositoryStore
    from app.clients.stars import StarStore
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


async def ensure_repository(
    store: RepositoryStore, owner: str, name: str, *, include_releases: bool = False
) -> RepositoryEntity:
    """Get an existing repository row or create one for the given owner and name.

    Args:
        store: Repository store.
        owner: Owner name (user or organization).
        name: Repository name.
        include_releases: Whether to eager-load the repository's releases.

    Returns:
        The repository entity.

    Raises:
        OwnerNotFoundError: If the owner cannot be resolved.
    """
    repository = await store.find_by_owner_and_name(owner, name, include_releases=include_releases)
    if repository is not None:
        return repository

    owner_id, _ = await store.resolve_owner(owner)
    repository = RepositoryEntity(name=name, owner_id=owner_id)
    await store.add(repository)
    return repository


class RepositoryService:
    """Service for browsing and managing Git repositories."""

    def __init__(
        self,
        backend: BlobBackend,
        blob_client: BlobStorageClient,
        redis_client: AbstractRedisClient,
        cache_client: AbstractCacheClient,
        repository_store: RepositoryStore,
        star_store: StarStore,
    ) -> None:
        """Initialize the repository service.

        Args:
            backend: Git backend.
            blob_client: Blob storage client.
            redis_client: Redis client.
            cache_client: Cache client for derived read responses.
            repository_store: Repository store used to enrich repository metadata with database records.
            star_store: Star store used to compute star counts.
        """
        self.backend = backend
        self.blob_client = blob_client
        self.redis_client = redis_client
        self.cache_client = cache_client
        self.repository_store = repository_store
        self.star_store = star_store

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

    async def cache_headers(self, owner: str, name: str, *, immutable: bool) -> dict[str, str]:
        """Compute CDN cache headers for repository content.

        Args:
            owner: Owner name.
            name: Repository name.
            immutable: Whether the content is addressed by an immutable commit SHA.

        Returns:
            Response headers instructing a CDN how to cache the content.
        """
        if await self._is_private(owner, name):
            return {"Cache-Control": CACHE_CONTROL_PRIVATE}
        if immutable:
            return {"Cache-Control": CACHE_CONTROL_IMMUTABLE}
        return {"Cache-Control": CACHE_CONTROL_REVALIDATE}

    async def _is_private(self, owner: str, name: str) -> bool:
        """Resolve whether a repository is private, caching the answer briefly.

        Args:
            owner: Owner name.
            name: Repository name.

        Returns:
            True if the repository exists and is private.
        """
        group = self._cache_group(owner, name)
        cached = await self.cache_client.get("private", group=group)
        if cached is not None:
            return cached == "1"
        entity = await self.repository_store.find_by_owner_and_name(owner, name)
        is_private = entity is not None and entity.is_private
        await self.cache_client.set("private", "1" if is_private else "0", ttl=settings.CACHE_TTL, group=group)
        return is_private

    @staticmethod
    def _build_schema(entity: RepositoryEntity, stars_count: int, forks_count: int) -> Repository:
        """Build a repository schema with explicit star and fork counts.

        Args:
            entity: The repository entity (with its owner loaded).
            stars_count: The repository's star count.
            forks_count: The repository's fork count.

        Returns:
            The public repository representation.
        """
        repository = Repository(
            name=entity.name,
            owner=entity.owner.name,
            description=entity.description,
            default_branch=entity.default_branch,
            is_private=entity.is_private,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )
        repository.stars_count = stars_count
        repository.forks_count = forks_count
        return repository

    async def _to_schema(self, entity: RepositoryEntity) -> Repository:
        """Convert a repository entity to its public schema.

        Args:
            entity: The repository entity (with its owner loaded).

        Returns:
            The public repository representation.
        """
        return self._build_schema(
            entity,
            await self.star_store.count_by_repo(entity.id),
            await self.repository_store.count_by_fork_of(entity.id),
        )

    async def _to_schemas(self, entities: list[RepositoryEntity]) -> list[Repository]:
        """Convert repository entities to public schemas with batched counts.

        Args:
            entities: The repository entities (with their owners loaded).

        Returns:
            The public repository representations.
        """
        ids = [entity.id for entity in entities]
        star_counts = await self.star_store.count_by_repos(ids)
        fork_counts = await self.repository_store.count_forks_by_repos(ids)
        return [
            self._build_schema(entity, star_counts.get(entity.id, 0), fork_counts.get(entity.id, 0))
            for entity in entities
        ]

    async def list_repositories(self) -> RepositoriesPublic:
        """List all repositories.

        Returns:
            RepositoriesPublic with the discovered repositories.
        """
        entities = await self.repository_store.get_all(offset=0, limit=10000)
        data = await self._to_schemas(entities)
        return RepositoriesPublic(data=data, count=len(data))

    async def get_user_repositories(self, owner_id: uuid.UUID, offset: int = 0, limit: int = 100) -> RepositoriesPublic:
        """List repositories owned by a principal.

        Args:
            owner_id: The principal id of the repository owner.
            offset: Pagination offset.
            limit: Maximum number of repositories.

        Returns:
            RepositoriesPublic with the owner's repositories.
        """
        entities = await self.repository_store.get_by_owner(owner_id, offset, limit)
        data = await self._to_schemas(entities)
        return RepositoriesPublic(data=data, count=len(data))

    async def get_repository(self, owner: str, name: str) -> Repository:
        """Get a specific repository.

        Args:
            owner: Owner name.
            name: Repository name.

        Returns:
            The repository.

        Raises:
            RepositoryNotFoundError: If the repository does not exist.
        """
        entity = await self.repository_store.get_by_owner_and_name(owner, name)
        return await self._to_schema(entity)

    async def create_repository(self, owner: str, name: str) -> Repository:
        """Create a new empty Git repository.

        Args:
            owner: Owner name.
            name: Repository name.

        Returns:
            The created repository.

        Raises:
            HTTPException: If the owner cannot be resolved.
        """
        key = repo_key(owner, name)

        self.backend.create_repository(key)
        changes = self.backend.get_repository_changes(key)
        if any(changes.values()):
            await save_repository_changes_to_storage(self.blob_client, self.redis_client, key, changes)
            self.backend.clear_repository_changes(key)

        await ensure_repository(self.repository_store, owner, name)
        entity = await self.repository_store.get_by_owner_and_name(owner, name)
        return await self._to_schema(entity)

    async def ensure_loaded(self, owner: str, name: str) -> None:
        """Ensure a repository is loaded into the backend, creating it if absent.

        Args:
            owner: Owner name.
            name: Repository name.

        Raises:
            HTTPException: If the owner cannot be resolved.
        """
        await ensure_repository(self.repository_store, owner, name)

        key = repo_key(owner, name)
        if self.backend.repository_exists(key):
            return

        packs, refs = await load_repository_from_storage(self.blob_client, self.redis_client, key)
        if packs or refs:
            self.backend.load_repository_from_data(key, packs, refs)
        else:
            self.backend.create_repository(key)

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

        await save_repository_changes_to_storage(self.blob_client, self.redis_client, key, changes)
        self.backend.clear_repository_changes(key)
        await self.cache_client.invalidate(self._cache_group(owner, name))

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

        packs, refs = await load_repository_from_storage(self.blob_client, self.redis_client, key)
        logger.debug("Loaded from storage: %s (packs=%d, refs=%d)", key, len(packs), len(refs))
        if packs or refs:
            return self.backend.load_repository_from_data(key, packs, refs)

        # A row without stored Git data is an empty repository, not a missing one.
        if await self.repository_store.find_by_owner_and_name(owner, name) is not None:
            return self.backend.create_repository(key)
        raise HTTPException(status_code=404, detail="Repository not found")

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
                    )
                )

            return TreeListing(entries=entries, tree_path=tree_path, ref=ref)

        return await self._cached_model(
            key=f"tree:{ref}:{tree_path}",
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

        return await self._cached_model(
            key=f"blob:{ref}:{file_path}",
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

            description = None
            is_private = False
            stars_count = 0
            forks_count = 0
            fork_of = None
            entity = await self.repository_store.find_by_owner_and_name(owner, name)
            if entity is not None:
                description = entity.description
                is_private = entity.is_private
                stars_count = await self.star_store.count_by_repo(entity.id)
                forks_count = await self.repository_store.count_by_fork_of(entity.id)
                if entity.fork_of is not None:
                    fork_of = f"{entity.fork_of.owner.name}/{entity.fork_of.name}"

            return RepositoryInfo(
                name=name,
                owner=owner,
                description=description,
                is_private=is_private,
                default_branch=default_branch,
                branch_count=branch_count,
                tag_count=tag_count,
                stars_count=stars_count,
                forks_count=forks_count,
                fork_of=fork_of,
                last_commit=last_commit,
            )

        return await self._cached_model(
            key=f"info:{ref}",
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

    async def list_commits(
        self, owner: str, name: str, ref: str = "main", offset: int = 0, limit: int = 50
    ) -> CommitsPublic:
        """List commits reachable from a ref, newest first.

        Args:
            owner: Owner name.
            name: Repository name.
            ref: Git ref to start the history from.
            offset: Number of commits to skip.
            limit: Maximum number of commits to return.

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
            for entry in repo.get_walker(include=[ObjectID(commit_sha)]):
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
            key=f"commits:{ref}:{offset}:{limit}",
            group=self._cache_group(owner, name),
            ttl=self._ttl_for_ref(ref),
            model=CommitsPublic,
            compute=compute,
        )

    async def get_commit(self, owner: str, name: str, sha: str) -> CommitDetail:
        """Get detailed information about a single commit, including its diff.

        Args:
            owner: Owner name.
            name: Repository name.
            sha: Full commit SHA.

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

            buffer = io.BytesIO()
            write_commit_diff(buffer, store, obj)
            files = self._parse_patch(buffer.getvalue().decode("utf-8", errors="replace"))

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
            key=f"commit:{sha}",
            group=self._cache_group(owner, name),
            ttl=settings.CACHE_IMMUTABLE_TTL,
            model=CommitDetail,
            compute=compute,
        )

    async def compare(self, owner: str, name: str, base_ref: str, head_ref: str) -> CompareResult:
        """List the files changed between two refs.

        Args:
            owner: Owner name.
            name: Repository name.
            base_ref: Base ref (branch, tag, or commit SHA).
            head_ref: Head ref (branch, tag, or commit SHA).

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

            buffer = io.BytesIO()
            write_tree_diff(buffer, store, base_commit.tree, head_commit.tree)
            files = self._parse_patch(buffer.getvalue().decode("utf-8", errors="replace"))

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
            key=f"compare:{base_ref}:{head_ref}",
            group=self._cache_group(owner, name),
            ttl=ttl,
            model=CompareResult,
            compute=compute,
        )

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
