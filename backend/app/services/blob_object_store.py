"""BlobStorage-based object store for Git pack storage.

This module provides an object store implementation that uses BlobStorage
for storing Git pack files. It's designed to work with dulwich's pack-based
object store infrastructure.
"""

from __future__ import annotations

import tempfile
from io import BytesIO
from typing import TYPE_CHECKING, Any, BinaryIO

from dulwich.object_format import DEFAULT_OBJECT_FORMAT, ObjectFormat
from dulwich.object_store import BucketBasedObjectStore
from dulwich.pack import (
    Pack,
    PackData,
    PackIndexer,
    PackStreamCopier,
    iter_sha1,
    load_pack_index_file,
    write_pack_index,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator


class BlobPackData(PackData):
    """PackData implementation that reads from in-memory data.

    This class wraps pack data that has been pre-fetched from BlobStorage storage.
    """

    def __init__(self, data: bytes, object_format: ObjectFormat | None = None) -> None:
        """Initialize BlobPackData with pre-fetched data.

        Args:
            data: The raw pack file data as bytes.
            object_format: Object format for this pack.
        """
        if object_format is None:
            object_format = DEFAULT_OBJECT_FORMAT

        # Create a BytesIO wrapper around the data
        self._data_bytes = data
        self._file = BytesIO(data)

        # Initialize the parent class with the file-like object
        super().__init__(filename="", file=self._file, object_format=object_format)

    def close(self) -> None:
        """Close the pack data."""
        self._file.close()


class BlobPack(Pack):
    """A Git pack object backed by BlobStorage storage.

    This pack implementation uses pre-fetched data from BlobStorage rather than
    reading from local files.
    """

    def __init__(self, basename: str, pack_data: bytes, index_data: bytes, object_format: ObjectFormat) -> None:
        """Initialize BlobPack with pre-fetched pack and index data.

        Args:
            basename: Base name for the pack (without extension).
            pack_data: The raw pack file data.
            index_data: The raw index file data.
            object_format: Object format for this pack.
        """
        super().__init__(basename, object_format=object_format)

        # Create lazy loaders that return pre-fetched data
        self._pack_data_bytes = pack_data
        self._index_data_bytes = index_data

        # Load the index immediately to get object format
        idx_file = BytesIO(index_data)
        self._idx = load_pack_index_file(basename + ".idx", idx_file, object_format)
        self._idx_load = None

        # Set up lazy loading for pack data
        self._data_load = lambda: BlobPackData(pack_data, object_format)
        self._data = None


class BlobObjectStore(BucketBasedObjectStore):
    """Object store implementation using BlobStorage for storage.

    This object store stores Git pack files in BlobStorage buckets. It's designed to be
    used with pre-loaded data since BlobStorage operations are async but dulwich expects
    synchronous operations.

    Usage:
        1. Create the store with an BlobStorage bucket binding
        2. Call load_packs() to pre-fetch pack data from BlobStorage
        3. Use the store with dulwich as normal
        4. Call flush() to write any pending changes back to BlobStorage
    """

    def __init__(self, object_format: ObjectFormat | None = None) -> None:
        """Initialize BlobObjectStore.

        Args:
            object_format: Object format (hash algorithm) for the repository.
        """
        super().__init__()

        if object_format is not None:
            self.object_format = object_format

        # Cache of pack names to (pack_data, index_data) tuples
        # This is populated by load_packs() and updated during operations
        self._loaded_packs: dict[str, tuple[bytes, bytes]] = {}

        # Pending uploads: basename -> (pack_data, index_data)
        self._pending_uploads: dict[str, tuple[bytes, bytes]] = {}

        # Pending deletes: set of basenames to delete
        self._pending_deletes: set[str] = set()

    def _iter_pack_names(self) -> Iterator[str]:
        """Iterate over pack file names.

        Returns:
            Iterator of pack basenames (without extension).
        """
        return iter(self._loaded_packs.keys())

    def _get_pack(self, name: str) -> Pack:
        """Get a Pack object by name.

        Args:
            name: The pack basename (without extension).

        Returns:
            A Pack object for the requested pack.

        Raises:
            KeyError: If the pack is not found.
        """
        if name not in self._loaded_packs:
            raise KeyError(f"Pack {name} not found")

        pack_data, index_data = self._loaded_packs[name]
        return BlobPack(name, pack_data, index_data, self.object_format)

    def _upload_pack(self, basename: str, pack_file: BinaryIO, index_file: BinaryIO) -> None:
        """Queue a pack for upload to BlobStorage.

        This method doesn't actually upload to BlobStorage (since that's async).
        Instead, it stores the data to be uploaded later via flush().

        Args:
            basename: The pack basename (SHA hash of contents).
            pack_file: File-like object containing pack data.
            index_file: File-like object containing index data.
        """
        pack_data = pack_file.read()
        index_data = index_file.read()

        # Store in pending uploads
        self._pending_uploads[basename] = (pack_data, index_data)

        # Also add to loaded packs so it's immediately available
        self._loaded_packs[basename] = (pack_data, index_data)

    def _remove_pack_by_name(self, name: str) -> None:
        """Queue a pack for deletion from BlobStorage.

        Args:
            name: The pack basename to remove.
        """
        self._pending_deletes.add(name)
        self._loaded_packs.pop(name, None)
        self._pending_uploads.pop(name, None)

    def load_packs_from_data(self, packs: dict[str, tuple[bytes, bytes]]) -> None:
        """Load pack data that was pre-fetched from BlobStorage.

        This method should be called after fetching pack data from BlobStorage
        asynchronously, before using the store with dulwich.

        Args:
            packs: Dictionary mapping pack basenames to (pack_data, index_data) tuples.
        """
        self._loaded_packs.update(packs)
        # Clear the pack cache to force reload
        self._pack_cache.clear()

    def get_pending_uploads(self) -> dict[str, tuple[bytes, bytes]]:
        """Get pending pack uploads.

        Returns:
            Dictionary mapping pack basenames to (pack_data, index_data) tuples.
        """
        return dict(self._pending_uploads)

    def get_pending_deletes(self) -> set[str]:
        """Get pending pack deletions.

        Returns:
            Set of pack basenames to delete.
        """
        return set(self._pending_deletes)

    def clear_pending(self) -> None:
        """Clear all pending uploads and deletes.

        Call this after successfully flushing changes to BlobStorage.
        """
        self._pending_uploads.clear()
        self._pending_deletes.clear()

    def add_pack(self) -> tuple[BinaryIO, Callable[[], Any], Callable[[], None]]:
        """Add a new pack to this object store.

        Returns:
            Tuple of (file_object, commit_function, abort_function).
        """
        # Use the parent implementation which calls _upload_pack
        return super().add_pack()

    def add_thin_pack(
        self,
        read_all: Callable[[int], bytes],
        read_some: Callable[[int], bytes] | None,
        progress: Callable[..., None] | None = None,
    ) -> Pack:
        """Add a new thin pack to this object store.

        Thin packs are packs that contain deltas with parents that exist
        outside the pack. They should never be placed in the object store
        directly, and always indexed and completed as they are copied.

        Args:
            read_all: Read function that blocks until the number of
                requested bytes are read.
            read_some: Read function that returns at least one byte, but may
                not return the number of bytes requested.
            progress: Optional progress reporting function.

        Returns:
            A Pack object pointing at the completed pack.
        """
        # Create a temp file for the pack data
        with tempfile.SpooledTemporaryFile(max_size=10 * 1024 * 1024, prefix="thin-pack-") as pf:
            # Use PackIndexer to resolve external refs and PackStreamCopier to copy
            indexer = PackIndexer(
                pf,
                self.object_format.hash_func,
                resolve_ext_ref=self.get_raw,
            )
            copier = PackStreamCopier(
                self.object_format.hash_func,
                read_all,
                read_some,
                pf,
                delta_iter=indexer,  # type: ignore[arg-type]
            )
            copier.verify(progress=progress)

            # Now complete the pack
            pf.seek(0)
            pack_data = pf.read()

        if len(pack_data) == 0:
            raise ValueError("Empty pack data")

        # Create PackData from the data
        pack_file = BytesIO(pack_data)
        p = PackData("", file=pack_file, object_format=self.object_format)

        # Get entries for index
        entries = p.sorted_entries()

        # Generate basename from SHA of entries
        basename = iter_sha1(entry[0] for entry in entries).decode("ascii")

        # Create index file
        idxf = BytesIO()
        checksum = p.get_stored_checksum()
        write_pack_index(idxf, entries, checksum, version=2)
        idxf.seek(0)
        idx_data = idxf.read()

        # Store the pack
        pack_file.seek(0)
        final_pack_data = pack_file.read()
        self._pending_uploads[basename] = (final_pack_data, idx_data)
        self._loaded_packs[basename] = (final_pack_data, idx_data)

        # Create and return the pack object
        pack_file.seek(0)
        idx = load_pack_index_file(basename + ".idx", BytesIO(idx_data), self.object_format)
        final_pack = Pack.from_objects(p, idx)
        self._add_cached_pack(basename, final_pack)

        return final_pack
