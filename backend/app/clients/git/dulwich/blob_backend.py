"""Blob-based backend for Git smart server.

This module provides a Backend implementation that uses blob storage for
object storage and Redis for refs.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from dulwich.errors import NotGitRepository
from dulwich.server import Backend

from app.clients.git.dulwich.blob_repository import BlobRepository

if TYPE_CHECKING:
    from app.types import PackContents, RepositoryChanges


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

    def remove_repository(self, path: str) -> None:
        """Evict a repository after deletion or rename."""
        self._repos.pop(self._normalize_path(path), None)
