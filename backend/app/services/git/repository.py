"""Request-local Git repositories with lazy, disk-backed cloud packs."""

from __future__ import annotations

import tempfile
from base64 import b64decode, b64encode
from functools import partial
from io import BytesIO
from typing import TYPE_CHECKING, BinaryIO, override

from anyio import from_thread
from dulwich.object_store import BucketBasedObjectStore, _bound_read_callables
from dulwich.objects import ObjectID, RawObjectID
from dulwich.pack import (
    Pack,
    PackData,
    PackIndexer,
    PackStreamCopier,
    extend_pack,
    load_pack_index_file,
    write_pack_index,
)
from dulwich.refs import HEADREF, LOCAL_BRANCH_PREFIX, Ref
from dulwich.repo import MemoryRepo

from app.config import settings

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator, Sequence

    from dulwich.object_format import ObjectFormat
    from dulwich.pack import PackIndex, PackIndexEntry

    from app.clients.blob_storage import BlobStorageClient
    from app.clients.cache import AbstractCacheClient
    from app.types import RepositoryChanges


MAX_CACHED_BYTES = 1024 * 1024


class BlobObjectStore(BucketBasedObjectStore):
    """Adapt cloud pack storage to Dulwich's lazy pack readers."""

    def __init__(
        self,
        blob: BlobStorageClient,
        prefix: str,
        names: set[str],
        object_format: ObjectFormat | None = None,
        cache: AbstractCacheClient | None = None,
    ) -> None:
        """Retain pack names; indexes and data are opened only when needed."""
        super().__init__(object_format=object_format)
        self.blob, self.prefix = blob, prefix
        self.cache = cache
        self.cache_group = f"git:{prefix.removesuffix('/packs/')}"
        self.names = set(names)
        self.pending_additions: set[str] = set()
        self.pending_deletes: set[str] = set()

    @override
    def _iter_pack_names(self) -> Iterator[str]:
        return iter(sorted(self.names))

    @override
    def _get_pack(self, name: str) -> Pack:
        def load_data() -> PackData:
            with self.blob.open(f"{self.prefix}{name}.pack") as stream:
                return PackData(name, file=stream, object_format=self.object_format)

        def load_index() -> PackIndex:
            key = f"index:{name}"
            if value := self._cached(key):
                return load_pack_index_file(name, BytesIO(b64decode(value)), self.object_format)
            with self.blob.open(f"{self.prefix}{name}.idx") as stream:
                index = load_pack_index_file(name, stream, self.object_format)
                stream.seek(0, 2)
                if stream.tell() <= MAX_CACHED_BYTES:
                    stream.seek(0)
                    self._cache(key, b64encode(stream.read()).decode())
                return index

        return Pack.from_lazy_objects(load_data, load_index)

    def _cached(self, key: str) -> str | None:
        return from_thread.run(partial(self.cache.get, key, group=self.cache_group)) if self.cache else None

    def _cache(self, key: str, value: str) -> None:
        if self.cache:
            from_thread.run(
                partial(self.cache.set, key, value, ttl=settings.CACHE_IMMUTABLE_TTL, group=self.cache_group)
            )

    @override
    def get_raw(self, name: RawObjectID | ObjectID) -> tuple[int, bytes]:
        key = "object:" + (name.hex() if len(name) == self.object_format.oid_length else name.decode())
        if value := self._cached(key):
            kind, data = value.split(":", 1)
            return int(kind), b64decode(data)
        kind, data = super().get_raw(name)
        if len(data) <= MAX_CACHED_BYTES:
            self._cache(key, f"{kind}:{b64encode(data).decode()}")
        return kind, data

    @override
    def _upload_pack(self, basename: str, pack_file: BinaryIO, index_file: BinaryIO) -> None:
        if basename not in self.names:
            self.blob.put(f"{self.prefix}{basename}.pack", pack_file)
            self.blob.put(f"{self.prefix}{basename}.idx", index_file)
            self.names.add(basename)
            self.pending_additions.add(basename)
        self.pending_deletes.discard(basename)

    @override
    def _remove_pack_by_name(self, name: str) -> None:
        self.pending_deletes.add(name)
        self.names.discard(name)
        self.pending_additions.discard(name)

    @override
    def add_pack(self) -> tuple[BinaryIO, Callable[[], None], Callable[[], None]]:
        """Upload a new pack without scanning existing pack data for duplicates."""
        stream = tempfile.TemporaryFile(prefix="incoming-")  # noqa: SIM115 - closed by commit/abort callbacks

        def commit() -> None:
            try:
                if stream.tell():
                    stream.seek(0)
                    with PackData("", file=stream, object_format=self.object_format) as pack:
                        entries, checksum = pack.sorted_entries(), pack.get_stored_checksum()
                    self._finish_pack(stream, entries, checksum)
            finally:
                stream.close()

        return stream, commit, stream.close

    def _finish_pack(self, stream: BinaryIO, entries: Sequence[PackIndexEntry], checksum: bytes) -> Pack:
        # The pack checksum identifies its encoding too, keeping retries and concurrent uploads immutable.
        basename = checksum.hex()
        index = BytesIO()
        write_pack_index(index, sorted(entries), checksum, version=2)
        stream.seek(0)
        index.seek(0)
        self._upload_pack(basename, stream, index)
        if len(index.getvalue()) <= MAX_CACHED_BYTES:
            self._cache(f"index:{basename}", b64encode(index.getvalue()).decode())
        result = self._get_pack(basename)
        self._add_cached_pack(basename, result)
        return result

    def add_thin_pack(
        self,
        read_all: Callable[[int], bytes],
        read_some: Callable[[int], bytes] | None,
        progress: Callable[..., None] | None = None,
        *,
        max_input_size: int | None = None,
    ) -> Pack:
        """Complete incoming deltas against existing objects before uploading the pack."""
        if max_input_size is not None:
            read_all, read_some = _bound_read_callables(read_all, read_some, max_input_size)
        with tempfile.TemporaryFile(prefix="thin-pack-") as pack_file:
            copier = PackStreamCopier(self.object_format.hash_func, read_all, read_some, pack_file)
            copier.verify(progress=progress)
            pack_file.seek(0)
            with PackData("", file=pack_file, object_format=self.object_format) as pack:
                indexer = PackIndexer.for_pack_data(pack, resolve_ext_ref=self.get_raw)
                entries = list(indexer)
                pack_sha, extra_entries = extend_pack(
                    pack_file,
                    set(indexer.ext_refs()),
                    self.get_raw,
                    self.object_format,
                    compression_level=self.pack_compression_level,
                    progress=progress,
                )
            entries.extend(extra_entries)
            return self._finish_pack(pack_file, entries, pack_sha)


class BlobRepository(MemoryRepo):
    """Use Dulwich's in-memory repository and refs, tracking persisted snapshots."""

    object_store: BlobObjectStore

    def __init__(
        self,
        blob: BlobStorageClient,
        prefix: str,
        names: set[str],
        object_format: ObjectFormat | None = None,
        cache: AbstractCacheClient | None = None,
    ) -> None:
        """Use a pack-backed object store while retaining MemoryRepo's behavior."""
        super().__init__()
        self.object_store = BlobObjectStore(blob, prefix, names, object_format, cache)
        self.object_format = self.object_store.object_format
        self._saved_refs: dict[bytes, bytes] = {}

    def load_from_storage(self, refs: dict[str, bytes]) -> None:
        """Install raw refs without treating them as pending writes."""
        for name, value in refs.items():
            if value.startswith(b"ref: "):
                self.refs.set_symbolic_ref(Ref(name.encode()), Ref(value[5:]))
            else:
                self.refs[Ref(name.encode())] = ObjectID(value)
        self.clear_pending_changes()

    def _raw_refs(self) -> dict[bytes, bytes]:
        return {
            bytes(name): value for name in self.refs.allkeys() if (value := self.refs.read_loose_ref(name)) is not None
        }

    def get_pending_changes(self) -> RepositoryChanges:
        """Return staged packs and refs changed since the last successful save."""
        refs = self._raw_refs()
        return {
            "pack_additions": set(self.object_store.pending_additions),
            "pack_deletes": set(self.object_store.pending_deletes),
            "ref_puts": {name: value for name, value in refs.items() if self._saved_refs.get(name) != value},
            "ref_deletes": self._saved_refs.keys() - refs.keys(),
        }

    def clear_pending_changes(self) -> None:
        """Advance the persisted snapshot after a successful save."""
        self.object_store.pending_additions.clear()
        self.object_store.pending_deletes.clear()
        self._saved_refs = self._raw_refs()

    @classmethod
    def create(
        cls,
        blob: BlobStorageClient,
        prefix: str,
        object_format: ObjectFormat | None = None,
        cache: AbstractCacheClient | None = None,
    ) -> BlobRepository:
        """Create a bare repository with main as its symbolic HEAD."""
        repo = cls(blob, prefix, set(), object_format, cache)
        repo.refs.set_symbolic_ref(HEADREF, Ref(LOCAL_BRANCH_PREFIX + b"main"))
        return repo
