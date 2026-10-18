"""Request-local Git repositories backed by preloaded pack bytes."""

from __future__ import annotations

import tempfile
from io import BytesIO
from typing import TYPE_CHECKING, BinaryIO, override

from dulwich.object_store import BucketBasedObjectStore, _bound_read_callables
from dulwich.objects import ObjectID
from dulwich.pack import (
    Pack,
    PackData,
    PackIndexer,
    PackStreamCopier,
    extend_pack,
    iter_sha1,
    load_pack_index_file,
    write_pack_index,
)
from dulwich.refs import HEADREF, LOCAL_BRANCH_PREFIX, Ref
from dulwich.repo import MemoryRepo

from app.types import PackContents, RepositoryChanges

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

    from dulwich.object_format import ObjectFormat


class BlobObjectStore(BucketBasedObjectStore):
    """Read preloaded packs and stage pack changes for asynchronous persistence."""

    def __init__(self, object_format: ObjectFormat | None = None) -> None:
        """Initialize request-local packs and pending writes."""
        super().__init__(object_format=object_format)
        self.packs_data: dict[str, PackContents] = {}
        self.pending_uploads: dict[str, PackContents] = {}
        self.pending_deletes: set[str] = set()

    @override
    def _iter_pack_names(self) -> Iterator[str]:
        return iter(self.packs_data)

    @override
    def _get_pack(self, name: str) -> Pack:
        contents = self.packs_data[name]
        index = load_pack_index_file(f"{name}.idx", BytesIO(contents.index), self.object_format)
        data = PackData("", file=BytesIO(contents.pack), object_format=self.object_format)
        return Pack.from_objects(data, index)

    @override
    def _upload_pack(self, basename: str, pack_file: BinaryIO, index_file: BinaryIO) -> None:
        contents = PackContents(pack=pack_file.read(), index=index_file.read())
        self.pending_uploads[basename] = self.packs_data[basename] = contents
        self.pending_deletes.discard(basename)

    @override
    def _remove_pack_by_name(self, name: str) -> None:
        self.pending_deletes.add(name)
        self.packs_data.pop(name, None)
        self.pending_uploads.pop(name, None)

    def load_packs_from_data(self, packs: dict[str, PackContents]) -> None:
        """Install downloaded packs and release any previous pack readers."""
        self.close()
        self.packs_data.update(packs)

    def add_thin_pack(
        self,
        read_all: Callable[[int], bytes],
        read_some: Callable[[int], bytes] | None,
        progress: Callable[..., None] | None = None,
        *,
        max_input_size: int | None = None,
    ) -> Pack:
        """Complete incoming deltas against existing objects before staging the pack."""
        if max_input_size is not None:
            read_all, read_some = _bound_read_callables(read_all, read_some, max_input_size)
        with tempfile.SpooledTemporaryFile(max_size=10 * 1024 * 1024, prefix="thin-pack-") as output:
            copier = PackStreamCopier(self.object_format.hash_func, read_all, read_some, output)
            copier.verify(progress=progress)
            output.seek(0)
            data = output.read()
        if not data:
            raise ValueError("Empty pack data")
        pack_file = BytesIO(data)
        with PackData("", file=BytesIO(data), object_format=self.object_format) as pack:
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
        entries.sort()
        basename = iter_sha1(entry[0] for entry in entries).decode("ascii")
        index_file = BytesIO()
        write_pack_index(index_file, entries, pack_sha, version=2)
        pack_file.seek(0)
        index_file.seek(0)
        self._upload_pack(basename, pack_file, index_file)
        result = self._get_pack(basename)
        self._add_cached_pack(basename, result)
        return result


class BlobRepository(MemoryRepo):
    """Use Dulwich's in-memory repository and refs, tracking persisted snapshots."""

    object_store: BlobObjectStore

    def __init__(self, object_format: ObjectFormat | None = None) -> None:
        """Use a pack-backed object store while retaining MemoryRepo's behavior."""
        super().__init__()
        self.object_store = BlobObjectStore(object_format)
        self.object_format = self.object_store.object_format
        self._saved_refs: dict[bytes, bytes] = {}

    def load_from_storage(self, packs: dict[str, PackContents], refs: dict[str, bytes]) -> None:
        """Load stored packs and raw refs without treating them as pending writes."""
        self.object_store.load_packs_from_data(packs)
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
            "pack_uploads": dict(self.object_store.pending_uploads),
            "pack_deletes": set(self.object_store.pending_deletes),
            "ref_puts": {name: value for name, value in refs.items() if self._saved_refs.get(name) != value},
            "ref_deletes": self._saved_refs.keys() - refs.keys(),
        }

    def clear_pending_changes(self) -> None:
        """Advance the persisted snapshot after a successful save."""
        self.object_store.pending_uploads.clear()
        self.object_store.pending_deletes.clear()
        self._saved_refs = self._raw_refs()

    @classmethod
    def create(cls, object_format: ObjectFormat | None = None) -> BlobRepository:
        """Create a bare repository with main as its symbolic HEAD."""
        repo = cls(object_format)
        repo.refs.set_symbolic_ref(HEADREF, Ref(LOCAL_BRANCH_PREFIX + b"main"))
        return repo
