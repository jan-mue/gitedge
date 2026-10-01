"""BlobStorage-based Git repository implementation.

This module provides a repository implementation that uses BlobStorage
for object storage and Redis for refs. It combines BlobObjectStore and
RedisRefsContainer into a complete repository.
"""

from __future__ import annotations

import contextlib
import sys
from io import BytesIO
from typing import TYPE_CHECKING, Any

from dulwich.config import Config, ConfigFile
from dulwich.errors import NoIndexPresent
from dulwich.filters import FilterBlobNormalizer, FilterContext, FilterRegistry
from dulwich.object_format import DEFAULT_OBJECT_FORMAT, ObjectFormat
from dulwich.rebase import MemoryRebaseStateManager
from dulwich.refs import HEADREF, LOCAL_BRANCH_PREFIX, Ref
from dulwich.repo import BaseRepo

from app.services.blob_object_store import BlobObjectStore
from app.services.redis_refs import RedisRefsContainer

if TYPE_CHECKING:
    from dulwich.index import Index
    from dulwich.rebase import RebaseStateManager

    from app.types import PackContents, RepositoryChanges


class BlobRepository(BaseRepo):
    """Git repository backed by BlobStorage and Redis.

    This repository implementation stores:
    - Git objects (packs) in BlobStorage
    - Git refs (branches, tags, HEAD) in Redis
    - Named files (config, description) in memory

    It's designed for use in environments where storage is accessed
    asynchronously. The workflow is:
    1. Load data from BlobStorage/Redis asynchronously before creating the repo
    2. Use the repo with dulwich synchronously
    3. Flush changes back to BlobStorage/Redis asynchronously after operations
    """

    filter_context: FilterContext | None

    def __init__(self, object_format: ObjectFormat | None = None) -> None:
        """Create a new BlobRepository.

        Args:
            object_format: Object format (hash algorithm) to use.
        """
        if object_format is None:
            object_format = DEFAULT_OBJECT_FORMAT

        self._object_store = BlobObjectStore(object_format=object_format)
        self._refs = RedisRefsContainer()

        BaseRepo.__init__(self, self._object_store, self._refs, object_format)

        self._named_files: dict[str, bytes] = {}
        self.bare = True
        self._config = ConfigFile()
        self._description: bytes | None = None
        self.filter_context = None
        self._reflog: list[Any] = []

    @property
    def blob_object_store(self) -> BlobObjectStore:
        """Get the BlobStorage object store.

        Returns:
            The BlobObjectStore instance.
        """
        return self._object_store

    @property
    def redis_refs(self) -> RedisRefsContainer:
        """Get the Redis refs container.

        Returns:
            The RedisRefsContainer instance.
        """
        return self._refs

    def load_from_storage(
        self,
        packs: dict[str, PackContents],
        refs: dict[str, bytes],
        named_files: dict[str, bytes] | None = None,
    ) -> None:
        """Load repository data from storage.

        This method should be called after fetching data from BlobStorage/Redis
        asynchronously, before using the repository with dulwich.

        Args:
            packs: Dict mapping pack basenames to PackContents.
            refs: Dict mapping ref names to their values.
            named_files: Optional dict of named files (config, description, etc.).
        """
        self._object_store.load_packs_from_data(packs)

        refs_bytes: dict[str, bytes] = {}
        for name, value in refs.items():
            if isinstance(name, bytes):
                refs_bytes[name.decode()] = value
            else:
                refs_bytes[name] = value
        self._refs.load_refs_from_data(refs_bytes)

        if named_files:
            self._named_files.update(named_files)

    def get_pending_changes(self) -> RepositoryChanges:
        """Get all pending changes to write back to storage.

        Returns:
            Dictionary with keys:
            - 'pack_uploads': Dict of pack basenames to PackContents
            - 'pack_deletes': Set of pack basenames to delete
            - 'ref_puts': Dict of ref names to new values
            - 'ref_deletes': Set of ref names to delete
        """
        return {
            "pack_uploads": self._object_store.get_pending_uploads(),
            "pack_deletes": self._object_store.get_pending_deletes(),
            "ref_puts": self._refs.get_pending_puts(),
            "ref_deletes": self._refs.get_pending_deletes(),
        }

    def clear_pending_changes(self) -> None:
        """Clear all pending changes.

        Call this after successfully writing changes to BlobStorage/Redis.
        """
        self._object_store.clear_pending()
        self._refs.clear_pending()

    def set_description(self, description: bytes) -> None:
        """Set the description for this repository.

        Args:
            description: Text to set as description.
        """
        self._description = description

    def get_description(self) -> bytes | None:
        """Get the description of this repository.

        Returns:
            Repository description as bytes, or None if not set.
        """
        return self._description

    def _determine_file_mode(self) -> bool:
        """Probe the file-system to determine whether permissions can be trusted.

        Returns:
            True if permissions can be trusted, False otherwise.
        """
        return sys.platform != "win32"

    def _determine_symlinks(self) -> bool:
        """Probe the file-system to determine whether symlinks can be created.

        Returns:
            True if symlinks can be created, False otherwise.
        """
        return sys.platform != "win32"

    def _put_named_file(self, path: str, contents: bytes) -> None:
        """Write a file to the control dir with the given name and contents.

        Args:
            path: The path to the file, relative to the control dir.
            contents: A string to write to the file.
        """
        self._named_files[path] = contents

    def _del_named_file(self, path: str) -> None:
        """Delete a named file.

        Args:
            path: The path to the file, relative to the control dir.
        """
        with contextlib.suppress(KeyError):
            del self._named_files[path]

    def get_named_file(
        self,
        path: str | bytes,
        basedir: str | None = None,  # noqa: ARG002
    ) -> BytesIO | None:
        """Get a file from the control dir with a specific name.

        Args:
            path: The path to the file, relative to the control dir.
            basedir: Optional base directory for the path (unused in BlobStorage impl).

        Returns:
            An open file object, or None if the file does not exist.
        """
        path_str = path.decode() if isinstance(path, bytes) else path
        contents = self._named_files.get(path_str, None)
        if contents is None:
            return None
        return BytesIO(contents)

    def open_index(self, config: Config | None = None) -> Index:  # noqa: ARG002
        """Fail to open index for this repo, since it is bare.

        Args:
            config: Configuration to consult for index settings (unused in BlobStorage impl).

        Raises:
            NoIndexPresent: Always raised since BlobRepository is always bare.
        """
        raise NoIndexPresent

    def get_config(self) -> ConfigFile:
        """Retrieve the config object.

        Returns:
            ConfigFile object.
        """
        return self._config

    def get_rebase_state_manager(self) -> RebaseStateManager:
        """Get the appropriate rebase state manager for this repository.

        Returns:
            MemoryRebaseStateManager instance.
        """
        return MemoryRebaseStateManager(self)

    def get_blob_normalizer(self, config: Config | None = None) -> FilterBlobNormalizer:
        """Return a BlobNormalizer object for check-in/checkout operations.

        Args:
            config: Configuration to consult for filter setup. If None, falls back to ``self.get_config_stack()``.

        Returns:
            FilterBlobNormalizer instance.
        """
        if config is None:
            config = self.get_config_stack()
        git_attributes = self.get_gitattributes()

        # Lazily create FilterContext if needed
        if self.filter_context is None:
            filter_registry = FilterRegistry(config, self)
            self.filter_context = FilterContext(filter_registry)
        else:
            # Refresh the context with current config to handle config changes
            self.filter_context.refresh_config(config)

        return FilterBlobNormalizer(config, git_attributes, filter_context=self.filter_context)

    @classmethod
    def init_bare(cls, object_format: ObjectFormat | None = None) -> BlobRepository:
        """Create a new bare repository.

        Args:
            object_format: Object format to use.

        Returns:
            A new BlobRepository instance with default refs set up.
        """
        repo = cls(object_format=object_format)

        default_branch = Ref(LOCAL_BRANCH_PREFIX + b"main")
        repo.refs.set_symbolic_ref(HEADREF, default_branch)

        return repo
