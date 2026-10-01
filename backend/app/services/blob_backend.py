"""Blob-based backend for Git smart server.

This module provides a Backend implementation that uses blob storage for
object storage and Redis for refs.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from dulwich.errors import NotGitRepository
from dulwich.server import Backend

from app.services.blob_repository import BlobRepository
from app.types import PackContents

if TYPE_CHECKING:
    from app.clients.blob_storage import BlobStorageClient
    from app.clients.redis import AbstractRedisClient
    from app.types import RepositoryChanges

logger = logging.getLogger(__name__)

# Key prefixes for blob and Redis storage
PACK_PREFIX = "packs/"
REF_PREFIX = "refs/"


class BlobBackend(Backend):
    """Backend implementation using blob storage and Redis.

    This backend manages Git repositories stored in blob storage (for objects)
    and Redis (for refs). Each repository is stored under a path prefix.

    Since blob/Redis operations are async but dulwich is sync, repositories must be
    loaded before use and flushed after changes.
    """

    def __init__(self) -> None:
        """Initialize BlobBackend."""
        super().__init__()
        self._repos: dict[str, BlobRepository] = {}

    def open_repository(self, path: str | bytes) -> BlobRepository:
        """Open a repository at the given path.

        The repository must have been pre-loaded via load_repository()
        before calling this method.

        Args:
            path: Path to the repository (e.g., "/user/repo.git")

        Returns:
            BlobRepository instance.

        Raises:
            NotGitRepository: If the repository hasn't been loaded.
        """
        path = self._normalize_path(path)

        if path not in self._repos:
            raise NotGitRepository(f"Repository not found: {path}")

        return self._repos[path]

    def _normalize_path(self, path: str | bytes) -> str:
        """Normalize a repository path.

        Args:
            path: Raw path from request (can be str or bytes).

        Returns:
            Normalized path as string.
        """
        if isinstance(path, bytes):
            path = path.decode("utf-8")
        path = path.strip("/")
        if not path.endswith(".git"):
            path = path + ".git"
        return path

    def create_repository(self, path: str) -> BlobRepository:
        """Create a new repository.

        Args:
            path: Path for the new repository.

        Returns:
            New BlobRepository instance.
        """
        path = self._normalize_path(path)
        repo = BlobRepository.init_bare()
        self._repos[path] = repo
        return repo

    def load_repository_from_data(
        self,
        path: str,
        packs: dict[str, PackContents],
        refs: dict[str, bytes],
        named_files: dict[str, bytes] | None = None,
    ) -> BlobRepository:
        """Load a repository from pre-fetched data.

        Args:
            path: Repository path.
            packs: Dict mapping pack basenames to PackContents.
            refs: Dict mapping ref names to values.
            named_files: Optional dict of named files.

        Returns:
            Loaded BlobRepository instance.
        """
        path = self._normalize_path(path)

        repo = BlobRepository()
        repo.load_from_storage(packs, refs, named_files)
        self._repos[path] = repo

        return repo

    def get_repository_changes(self, path: str) -> RepositoryChanges:
        """Get pending changes for a repository.

        Args:
            path: Repository path.

        Returns:
            Dict of pending changes to write to storage.
        """
        path = self._normalize_path(path)
        if path not in self._repos:
            return {}
        return self._repos[path].get_pending_changes()

    def clear_repository_changes(self, path: str) -> None:
        """Clear pending changes for a repository.

        Args:
            path: Repository path.
        """
        path = self._normalize_path(path)
        if path in self._repos:
            self._repos[path].clear_pending_changes()

    def repository_exists(self, path: str) -> bool:
        """Check if a repository exists in the cache.

        Args:
            path: Repository path.

        Returns:
            True if repository is loaded, False otherwise.
        """
        return self._normalize_path(path) in self._repos


async def load_repository_from_storage(
    blob_client: BlobStorageClient,
    redis_client: AbstractRedisClient,
    repo_path: str,
) -> tuple[dict[str, PackContents], dict[str, bytes]]:
    """Load repository data from blob storage and Redis.

    Args:
        blob_client: Blob storage client instance.
        redis_client: Redis client instance.
        repo_path: Repository path prefix.

    Returns:
        Tuple of (packs_dict, refs_dict) to pass to load_repository_from_data.
    """
    repo_prefix = repo_path.strip("/")
    if not repo_prefix.endswith(".git"):
        repo_prefix = repo_prefix + ".git"

    packs: dict[str, PackContents] = {}
    pack_prefix = f"{repo_prefix}/{PACK_PREFIX}"

    pack_keys: dict[str, str] = {}
    idx_keys: dict[str, str] = {}
    for key in await blob_client.list_keys(pack_prefix):
        name = key.removeprefix(pack_prefix)
        if name.endswith(".pack"):
            pack_keys[name.removesuffix(".pack")] = key
        elif name.endswith(".idx"):
            idx_keys[name.removesuffix(".idx")] = key

    for basename, pack_key in pack_keys.items():
        idx_key = idx_keys.get(basename)
        if idx_key is None:
            continue
        pack_data = await blob_client.get(pack_key)
        idx_data = await blob_client.get(idx_key)
        if pack_data and idx_data:
            packs[basename] = PackContents(pack=pack_data, index=idx_data)

    refs: dict[str, bytes] = {}
    ref_prefix = f"{repo_prefix}/{REF_PREFIX}"

    for key in await redis_client.scan_keys(f"{ref_prefix}*"):
        value = await redis_client.get(key)
        if value:
            refs[key.removeprefix(ref_prefix)] = value

    return packs, refs


async def save_repository_changes_to_storage(
    blob_client: BlobStorageClient,
    redis_client: AbstractRedisClient,
    repo_path: str,
    changes: RepositoryChanges,
) -> None:
    """Save repository changes to blob storage and Redis.

    Args:
        blob_client: Blob storage client instance.
        redis_client: Redis client instance.
        repo_path: Repository path prefix.
        changes: Changes dict from get_pending_changes().
    """
    repo_prefix = repo_path.strip("/")
    if not repo_prefix.endswith(".git"):
        repo_prefix = repo_prefix + ".git"

    pack_prefix = f"{repo_prefix}/{PACK_PREFIX}"
    ref_prefix = f"{repo_prefix}/{REF_PREFIX}"

    for basename, contents in changes.get("pack_uploads", {}).items():
        pack_key = f"{pack_prefix}{basename}.pack"
        idx_key = f"{pack_prefix}{basename}.idx"
        await blob_client.put(pack_key, contents.pack)
        await blob_client.put(idx_key, contents.index)

    for basename in changes.get("pack_deletes", set()):
        pack_key = f"{pack_prefix}{basename}.pack"
        idx_key = f"{pack_prefix}{basename}.idx"
        await blob_client.delete(pack_key)
        await blob_client.delete(idx_key)

    for ref_name, value in changes.get("ref_puts", {}).items():
        ref_name_str = ref_name.decode() if isinstance(ref_name, bytes) else ref_name
        redis_key = f"{ref_prefix}{ref_name_str}"
        value_str = value.decode() if isinstance(value, bytes) else value
        await redis_client.set(redis_key, value_str)

    for ref_name in changes.get("ref_deletes", set()):
        ref_name_str = ref_name.decode() if isinstance(ref_name, bytes) else ref_name
        redis_key = f"{ref_prefix}{ref_name_str}"
        await redis_client.delete(redis_key)
