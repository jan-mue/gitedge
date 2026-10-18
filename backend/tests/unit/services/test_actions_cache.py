import hashlib
import io
import json
import tarfile

import pytest

from app.services.actions.cache import cache_blobs, restore_archive


def state(keys: list[str], *, artifact: bool = False) -> bytes:
    entries = [
        {"key": key, "version": "v1", "id": hashlib.sha256(f"{key}\0v1".encode()).hexdigest(), "created": 1}
        for key in keys
    ]
    files = {f"cache/{entry['id']}": str(entry["key"]).encode() for entry in entries}
    files["cache/index.json"] = json.dumps(entries).encode()
    if artifact:
        files["artifacts/123/example/result.zip"] = b"run artifact"
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w:gz") as archive:
        for name, data in files.items():
            member = tarfile.TarInfo(name)
            member.size = len(data)
            archive.addfile(member, io.BytesIO(data))
    return output.getvalue()


def test_parallel_cache_entries_survive_empty_jobs_without_leaking_artifacts() -> None:
    first = cache_blobs(state(["python"], artifact=True))
    second = cache_blobs(state(["bun"]))
    assert cache_blobs(state([])) == {}
    assert not set(first).intersection(second)
    archives = [*first.values(), *second.values()]
    restored = restore_archive(state([], artifact=True), archives)
    with tarfile.open(fileobj=io.BytesIO(restored), mode="r:gz") as archive:
        index = archive.extractfile("cache/index.json")
        assert index is not None
        entries = json.loads(index.read())
        assert {entry["key"] for entry in entries} == {"python", "bun"}
        for entry in entries:
            payload = archive.extractfile(f"cache/{entry['id']}")
            assert payload is not None
            assert payload.read() == entry["key"].encode()
        artifact = archive.extractfile("artifacts/123/example/result.zip")
        assert artifact is not None
        assert artifact.read() == b"run artifact"
    for data in archives:
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as archive:
            assert all(member.name.startswith("cache/") for member in archive)


def test_restore_rejects_artifact_symlinks_instead_of_extracting_them() -> None:
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w:gz") as archive:
        link = tarfile.TarInfo("artifacts/escape")
        link.type = tarfile.SYMTYPE
        link.linkname = "/etc/passwd"
        archive.addfile(link)
    with pytest.raises(ValueError, match="non-file"):
        restore_archive(output.getvalue(), [])
