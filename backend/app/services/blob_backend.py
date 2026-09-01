"""Blob-based backend for Git smart server.

This module provides a Backend implementation that uses blob storage for
object storage and Redis for refs.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from dulwich.errors import NotGitRepository
from dulwich.server import Backend

from app.clients.redis import redis_delete, redis_get, redis_scan_keys, redis_set
from app.services.blob_repository import BlobRepository

if TYPE_CHECKING:
    from app.clients.blob_storage import BlobStorageClient
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
        # Cache of loaded repositories
        self._repos: dict[str, BlobRepository] = {}

    def open_repository(self, path: str | bytes) -> BlobRepository:  # type: ignore[override]
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
        packs: dict[str, tuple[bytes, bytes]],
        refs: dict[str, bytes],
        named_files: dict[str, bytes] | None = None,
    ) -> BlobRepository:
        """Load a repository from pre-fetched data.

        Args:
            path: Repository path.
            packs: Dict mapping pack basenames to (pack_data, index_data).
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
    repo_path: str,
) -> tuple[dict[str, tuple[bytes, bytes]], dict[str, bytes]]:
    """Load repository data from blob storage and Redis.

    Args:
        blob_client: Blob storage client instance.
        repo_path: Repository path prefix.

    Returns:
        Tuple of (packs_dict, refs_dict) to pass to load_repository_from_data.
    """
    # Normalize path for storage keys
    repo_prefix = repo_path.strip("/")
    if not repo_prefix.endswith(".git"):
        repo_prefix = repo_prefix + ".git"

    # Load packs from blob storage
    packs: dict[str, tuple[bytes, bytes]] = {}
    pack_prefix = f"{repo_prefix}/{PACK_PREFIX}"

    # List all pack files
    all_keys = await blob_client.list_keys(pack_prefix)

    # Group by basename (without .pack/.idx extension)
    pack_files: dict[str, dict[str, str]] = {}
    for key in all_keys:
        if key.endswith(".pack"):
            basename = key[len(pack_prefix) : -5]  # Remove prefix and .pack
            if basename not in pack_files:
                pack_files[basename] = {}
            pack_files[basename]["pack_key"] = key
        elif key.endswith(".idx"):
            basename = key[len(pack_prefix) : -4]  # Remove prefix and .idx
            if basename not in pack_files:
                pack_files[basename] = {}
            pack_files[basename]["idx_key"] = key

    # Fetch pack and index data
    for basename, files in pack_files.items():
        if "pack_key" in files and "idx_key" in files:
            pack_data = await blob_client.get(files["pack_key"])
            idx_data = await blob_client.get(files["idx_key"])

            if pack_data and idx_data:
                packs[basename] = (pack_data, idx_data)

    # Load refs from Redis
    refs: dict[str, bytes] = {}
    ref_prefix = f"{repo_prefix}/{REF_PREFIX}"

    # Scan for all ref keys
    ref_keys = await redis_scan_keys(f"{ref_prefix}*")

    for key in ref_keys:
        ref_name = key[len(ref_prefix) :]  # Remove prefix to get ref name
        value = await redis_get(key)
        if value:
            refs[ref_name] = value

    return packs, refs


async def save_repository_changes_to_storage(
    blob_client: BlobStorageClient,
    repo_path: str,
    changes: RepositoryChanges,
) -> None:
    """Save repository changes to blob storage and Redis.

    Args:
        blob_client: Blob storage client instance.
        repo_path: Repository path prefix.
        changes: Changes dict from get_pending_changes().
    """
    # Normalize path for storage keys
    repo_prefix = repo_path.strip("/")
    if not repo_prefix.endswith(".git"):
        repo_prefix = repo_prefix + ".git"

    pack_prefix = f"{repo_prefix}/{PACK_PREFIX}"
    ref_prefix = f"{repo_prefix}/{REF_PREFIX}"

    # Upload new packs
    for basename, (pack_data, idx_data) in changes.get("pack_uploads", {}).items():
        pack_key = f"{pack_prefix}{basename}.pack"
        idx_key = f"{pack_prefix}{basename}.idx"
        await blob_client.put(pack_key, pack_data)
        await blob_client.put(idx_key, idx_data)

    # Delete removed packs
    for basename in changes.get("pack_deletes", set()):
        pack_key = f"{pack_prefix}{basename}.pack"
        idx_key = f"{pack_prefix}{basename}.idx"
        await blob_client.delete(pack_key)
        await blob_client.delete(idx_key)

    # Update refs
    for ref_name, value in changes.get("ref_puts", {}).items():
        ref_name_str = ref_name.decode() if isinstance(ref_name, bytes) else ref_name
        redis_key = f"{ref_prefix}{ref_name_str}"
        value_str = value.decode() if isinstance(value, bytes) else value
        await redis_set(redis_key, value_str)

    # Delete refs
    for ref_name in changes.get("ref_deletes", set()):
        ref_name_str = ref_name.decode() if isinstance(ref_name, bytes) else ref_name
        redis_key = f"{ref_prefix}{ref_name_str}"
        await redis_delete(redis_key)
