"""Repository metadata and policy using the Git client."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from fastapi import HTTPException

from app.config import settings
from app.entities.repositories import Repository as RepositoryEntity
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
    MergeSettings,
    ReadmeContent,
    RepositoriesPublic,
    Repository,
    RepositoryInfo,
    RepositoryStatistics,
    RepositoryUpdate,
    TreeListing,
)
from app.utils.cache_headers import (
    CACHE_CONTROL_IMMUTABLE,
    CACHE_CONTROL_PRIVATE,
    CACHE_CONTROL_REVALIDATE,
)

if TYPE_CHECKING:
    import uuid

    from app.clients.cache import AbstractCacheClient
    from app.clients.git.repositories import GitClient
    from app.clients.repositories import RepositoryStore
    from app.clients.stars import StarStore
    from app.entities.users import User
    from app.schemas.releases import TagsPublic
    from app.schemas.repository_activity import GitActivityHistory


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
    """Repository metadata and policy using the Git client."""

    def __init__(
        self,
        git: GitClient,
        cache_client: AbstractCacheClient,
        repository_store: RepositoryStore,
        star_store: StarStore,
    ) -> None:
        """Bind the Git client, metadata stores, and response cache."""
        self.git = git
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
            **{key: getattr(entity, key) for key in MergeSettings.model_fields},
            name=entity.name,
            owner=entity.owner.name,
            description=entity.description,
            default_branch=entity.default_branch,
            is_private=entity.is_private,
            fork_of=f"{entity.fork_of.owner.name}/{entity.fork_of.name}" if entity.fork_of is not None else None,
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

    async def _editable_repository(self, owner: str, name: str, user: User) -> RepositoryEntity:
        """Resolve a repository and require its owner or an administrator."""
        entity = await self.repository_store.get_by_owner_and_name(owner, name)
        if entity.owner_id != user.id and not user.is_superuser:
            raise HTTPException(status_code=403, detail="Only the repository owner can change settings")
        return entity

    async def delete_repository(self, owner: str, name: str, user: User) -> None:
        """Delete repository data and metadata, retaining independent forks."""
        entity = await self._editable_repository(owner, name, user)
        owner = entity.owner.name
        forks = await self.repository_store.list_by_fork_of(entity.id, limit=10000)
        await self.git.delete_repository(owner, name)
        await self.repository_store.delete(entity)
        await self.cache_client.invalidate(self._cache_group(owner, name))
        for fork in forks:
            await self.cache_client.invalidate(self._cache_group(fork.owner.name, fork.name))
        if entity.fork_of is not None:
            await self.cache_client.invalidate(self._cache_group(entity.fork_of.owner.name, entity.fork_of.name))

    async def create_repository(self, owner: str, name: str) -> Repository:
        """Create Git storage and its metadata record."""
        await self.git.create_repository(owner, name)
        await ensure_repository(self.repository_store, owner, name)
        entity = await self.repository_store.get_by_owner_and_name(owner, name)
        return await self._to_schema(entity)

    async def ensure_loaded(self, owner: str, name: str) -> None:
        """Ensure metadata exists before handling a Git protocol request."""
        await ensure_repository(self.repository_store, owner, name)
        await self.git.ensure_loaded(owner, name)

    async def save_changes(self, owner: str, name: str) -> None:
        """Persist objects before refs and invalidate repository responses."""
        await self.git.save_changes(owner, name)

    async def copy_repository(self, owner: str, name: str, target_owner: str, target_name: str) -> None:
        """Copy a repository and invalidate source and destination metadata."""
        await self.git.copy_repository(owner, name, target_owner, target_name)
        await self.cache_client.invalidate(self._cache_group(target_owner, target_name))
        await self.cache_client.invalidate(self._cache_group(owner, name))

    async def update_repository(self, owner: str, name: str, body: RepositoryUpdate, user: User) -> Repository:
        """Save settings, keeping Git storage and the default HEAD in sync."""
        entity = await self._editable_repository(owner, name, user)
        owner = entity.owner.name
        new_name = body.name or name
        if new_name in (".", "..") or new_name.endswith(".git"):
            raise HTTPException(status_code=400, detail="Invalid repository name")
        if new_name != name and await self.repository_store.find_by_owner_and_name(owner, new_name) is not None:
            raise HTTPException(status_code=409, detail="A repository with that name already exists")
        if body.default_branch is not None and body.default_branch != entity.default_branch:
            await self.git.set_default_branch(owner, name, body.default_branch)
        if new_name != name:
            await self.git.copy_repository(owner, name, owner, new_name)
        changes = body.model_dump(exclude_unset=True)
        changes = {key: value for key, value in changes.items() if value is not None or key == "description"}
        await self.repository_store.update(entity, changes)
        entity = await self.repository_store.get_by_owner_and_name(owner, new_name)
        if new_name != name:
            await self.git.delete_repository(owner, name)
        await self.cache_client.invalidate(self._cache_group(owner, name))
        await self.cache_client.invalidate(self._cache_group(owner, new_name))
        if entity.fork_of is not None:
            await self.cache_client.invalidate(self._cache_group(entity.fork_of.owner.name, entity.fork_of.name))
        return await self._to_schema(entity)

    async def get_file_index(self, owner: str, name: str, ref: str) -> FileIndex:
        """Delegate get file index to the configured Git engine."""
        return await self.git.get_file_index(owner, name, ref)

    async def get_statistics(self, owner: str, name: str, ref: str) -> RepositoryStatistics:
        """Delegate get statistics to the configured Git engine."""
        return await self.git.get_statistics(owner, name, ref)

    async def get_blame(self, owner: str, name: str, ref: str, file_path: str) -> BlameContent:
        """Delegate get blame to the configured Git engine."""
        return await self.git.get_blame(owner, name, ref, file_path)

    async def get_raw(self, owner: str, name: str, ref: str, file_path: str, *, follow_symlinks: bool = False) -> bytes:
        """Delegate get raw to the configured Git engine."""
        return await self.git.get_raw(owner, name, ref, file_path, follow_symlinks=follow_symlinks)

    async def get_source(self, owner: str, name: str, ref: str, path: str) -> TreeListing | FileContent:
        """Delegate get source to the configured Git engine."""
        return await self.git.get_source(owner, name, ref, path)

    async def get_tree(self, owner: str, name: str, ref: str, tree_path: str) -> TreeListing:
        """Delegate get tree to the configured Git engine."""
        return await self.git.get_tree(owner, name, ref, tree_path)

    async def get_blob(self, owner: str, name: str, ref: str, file_path: str) -> FileContent:
        """Delegate get blob to the configured Git engine."""
        return await self.git.get_blob(owner, name, ref, file_path)

    async def get_info(self, owner: str, name: str, ref: str) -> RepositoryInfo:
        """Enrich engine-neutral Git information with current repository metadata."""
        group = self._cache_group(owner, name)
        key = f"info:v2:{ref}"
        cached = await self.cache_client.get(key, group=group)
        if cached is not None:
            return RepositoryInfo.model_validate_json(cached)
        info = (await self.git.get_info(owner, name, ref)).model_copy(deep=True)
        entity = await self.repository_store.find_by_owner_and_name(owner, name)
        if entity is not None:
            info.description = entity.description
            info.is_private = entity.is_private
            info.stars_count = await self.star_store.count_by_repo(entity.id)
            info.forks_count = await self.repository_store.count_by_fork_of(entity.id)
            if entity.fork_of is not None:
                info.fork_of = f"{entity.fork_of.owner.name}/{entity.fork_of.name}"
        await self.cache_client.set(key, info.model_dump_json(), ttl=settings.CACHE_TTL, group=group)
        return info

    async def get_readme(self, owner: str, name: str, ref: str, tree_path: str) -> ReadmeContent:
        """Delegate get readme to the configured Git engine."""
        return await self.git.get_readme(owner, name, ref, tree_path)

    async def list_branches(self, owner: str, name: str) -> list[BranchInfo]:
        """Delegate list branches to the configured Git engine."""
        return await self.git.list_branches(owner, name)

    async def list_tags(self, owner: str, name: str) -> TagsPublic:
        """Delegate list tags to the configured Git engine."""
        return await self.git.list_tags(owner, name)

    async def activity_history(self, owner: str, name: str) -> GitActivityHistory:
        """Delegate activity history to the configured Git engine."""
        return await self.git.activity_history(owner, name)

    async def list_commits(
        self, owner: str, name: str, ref: str = "main", offset: int = 0, limit: int = 50, file_path: str = ""
    ) -> CommitsPublic:
        """Delegate list commits to the configured Git engine."""
        return await self.git.list_commits(owner, name, ref, offset, limit, file_path)

    async def get_commit(self, owner: str, name: str, sha: str, *, include_diff: bool = True) -> CommitDetail:
        """Delegate get commit to the configured Git engine."""
        return await self.git.get_commit(owner, name, sha, include_diff=include_diff)

    async def branch_heads(self, owner: str, name: str, base: str, head: str) -> tuple[str | None, str | None]:
        """Delegate branch heads to the configured Git engine."""
        return await self.git.branch_heads(owner, name, base, head)

    async def compare_commits(
        self, owner: str, name: str, base_ref: str, head_ref: str, offset: int = 0, limit: int = 50
    ) -> CommitsPublic:
        """Delegate compare commits to the configured Git engine."""
        return await self.git.compare_commits(owner, name, base_ref, head_ref, offset, limit)

    async def compare(
        self, owner: str, name: str, base_ref: str, head_ref: str, *, include_diff: bool = True
    ) -> CompareResult:
        """Delegate compare to the configured Git engine."""
        return await self.git.compare(owner, name, base_ref, head_ref, include_diff=include_diff)

    async def get_diff_file(self, owner: str, name: str, head: str, file_path: str, base: str = "") -> CommitFileChange:
        """Delegate get diff file to the configured Git engine."""
        return await self.git.get_diff_file(owner, name, head, file_path, base)

    async def get_diff_context(
        self, owner: str, name: str, base: str, head: str, path: str, side: Literal["old", "new"], line: int
    ) -> DiffHunk:
        """Delegate get diff context to the configured Git engine."""
        return await self.git.get_diff_context(owner, name, base, head, path, side, line)

    async def action_revision(self, owner: str, name: str, ref: str) -> tuple[str, str]:
        """Resolve an immutable Actions commit and its canonical ref."""
        return await self.git.action_revision(owner, name, ref)

    async def action_refs(self, owner: str, name: str) -> dict[str, str]:
        """Snapshot branch and tag tips for authenticated push events."""
        return await self.git.action_refs(owner, name)
