"""Bounded cache archives with independent, content-addressed entry blobs."""

import hashlib
import io
import json
import tarfile
from pathlib import PurePosixPath

from pydantic import Field

from app.schemas.base import GitEdgeBaseModel

STATE_LIMIT = 32 * 1024 * 1024
MAX_CACHE_ENTRIES = 128


class CacheEntry(GitEdgeBaseModel):
    """Metadata written by either version of the job-local cache protocol."""

    id: str = Field(pattern=r"^[a-f0-9]{64}$")
    key: str = Field(min_length=1, max_length=512)
    version: str = Field(min_length=1, max_length=512)
    created: float = Field(ge=0, allow_inf_nan=False)


def _read(archive: tarfile.TarFile, member: tarfile.TarInfo, budget: int) -> bytes:
    if not member.isfile() or member.size > budget:
        raise ValueError("State archive exceeds the transfer limit or contains a non-file entry")
    stream = archive.extractfile(member)
    if stream is None:
        raise ValueError("Missing archive entry")
    return stream.read(budget + 1)


def _pack(files: dict[str, bytes]) -> bytes:
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w:gz") as archive:
        for name, data in files.items():
            member = tarfile.TarInfo(name)
            member.mode = 0o600
            member.size = len(data)
            archive.addfile(member, io.BytesIO(data))
    if output.tell() > STATE_LIMIT:
        raise ValueError("State archive exceeds the transfer limit")
    return output.getvalue()


def _entries(data: bytes) -> list[tuple[CacheEntry, bytes]]:
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as archive:
        try:
            index = archive.getmember("cache/index.json")
        except KeyError:
            return []
        raw = json.loads(_read(archive, index, STATE_LIMIT))
        if not isinstance(raw, list) or len(raw) > MAX_CACHE_ENTRIES:
            raise ValueError("Invalid cache index or too many cache entries")
        entries = []
        budget = STATE_LIMIT
        for item in raw:
            entry = CacheEntry.model_validate(item)
            expected = hashlib.sha256(f"{entry.key}\0{entry.version}".encode()).hexdigest()
            if entry.id != expected:
                raise ValueError("Cache identifier does not match its key/version")
            payload = _read(archive, archive.getmember(f"cache/{entry.id}"), budget)
            budget -= len(payload)
            entries.append((entry, payload))
        return entries


def cache_blobs(data: bytes) -> dict[str, bytes]:
    """Split a job archive so parallel writers cannot erase unrelated cache keys."""
    return {
        entry.id: _pack({"cache/index.json": json.dumps([entry.model_dump()]).encode(), f"cache/{entry.id}": payload})
        for entry, payload in _entries(data)
    }


def restore_archive(state: bytes | None, caches: list[bytes]) -> bytes:
    """Overlay all cache keys while retaining the current run's artifact state."""
    files: dict[str, bytes] = {}
    budget = STATE_LIMIT
    entries: dict[str, tuple[CacheEntry, bytes]] = {}
    if state:
        entries.update((entry.id, (entry, payload)) for entry, payload in _entries(state))
        with tarfile.open(fileobj=io.BytesIO(state), mode="r:gz") as archive:
            for member in archive:
                path = PurePosixPath(member.name)
                if not path.parts or path.parts[0] != "artifacts" or member.isdir():
                    continue
                if ".." in path.parts or path.is_absolute():
                    raise ValueError("Unsafe artifact path in state archive")
                files[str(path)] = _read(archive, member, budget)
                budget -= len(files[str(path)])
    for cache in caches:
        for entry, payload in _entries(cache):
            existing = entries.get(entry.id)
            if existing is None or entry.created > existing[0].created:
                entries[entry.id] = (entry, payload)
    selected = []
    for entry, payload in sorted(entries.values(), key=lambda item: item[0].created, reverse=True):
        if len(selected) >= MAX_CACHE_ENTRIES or len(payload) > budget:
            continue
        selected.append(entry.model_dump())
        files[f"cache/{entry.id}"] = payload
        budget -= len(payload)
    files["cache/index.json"] = json.dumps(selected).encode()
    return _pack(files)
