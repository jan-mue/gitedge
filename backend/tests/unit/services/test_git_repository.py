"""Git ref snapshots and real thin-pack ingestion without external services."""

import subprocess
from io import BytesIO
from typing import TYPE_CHECKING

from dulwich.objects import ObjectID
from dulwich.pack import PackData
from dulwich.refs import Ref

from app.services.git.repository import BlobRepository

if TYPE_CHECKING:
    from pathlib import Path


OLD = ObjectID(b"1" * 40)
NEW = ObjectID(b"2" * 40)
MAIN = Ref(b"refs/heads/main")


def test_loaded_symbolic_refs_are_clean_and_only_real_changes_are_staged() -> None:
    repo = BlobRepository()
    repo.load_from_storage({}, {"HEAD": b"ref: refs/heads/main", "refs/heads/main": OLD})
    assert not any(repo.get_pending_changes().values())
    assert repo.refs[Ref(b"HEAD")] == OLD
    assert not repo.refs.set_if_equals(MAIN, NEW, NEW)
    assert repo.refs.set_if_equals(MAIN, OLD, NEW)
    assert repo.get_pending_changes()["ref_puts"] == {bytes(MAIN): NEW}
    assert repo.refs.set_if_equals(MAIN, NEW, OLD)
    assert not any(repo.get_pending_changes().values())
    assert repo.refs.remove_if_equals(MAIN, OLD)
    assert repo.get_pending_changes()["ref_deletes"] == {bytes(MAIN)}
    repo.clear_pending_changes()
    assert not any(repo.get_pending_changes().values())
    repo.close()


def test_new_symbolic_head_is_saved_once() -> None:
    repo = BlobRepository.create()
    assert repo.get_pending_changes()["ref_puts"] == {b"HEAD": b"ref: refs/heads/main"}
    repo.clear_pending_changes()
    repo.refs.set_symbolic_ref(Ref(b"HEAD"), MAIN)
    assert not any(repo.get_pending_changes().values())
    repo.close()


def test_real_git_thin_pack_is_completed_and_survives_reload(tmp_path: Path) -> None:
    def git(*args: str, data: bytes | None = None) -> bytes:
        return subprocess.run(["git", "-C", str(tmp_path), *args], input=data, capture_output=True, check=True).stdout

    git("init", "--initial-branch=main")
    original = "".join(f"line {index}: original content for delta compression\n" for index in range(10000))
    path = tmp_path / "data.txt"
    path.write_text(original)

    def commit(message: str) -> bytes:
        git("add", "data.txt")
        git("-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-m", message)
        return git("rev-parse", "HEAD").strip()

    base = commit("Base")
    repo = BlobRepository.create()
    packed = git("pack-objects", "--stdout", "--revs", data=base + b"\n")
    repo.object_store.add_thin_pack(BytesIO(packed).read, None)
    repo.clear_pending_changes()
    path.write_text(original.replace("line 5000:", "changed 5000:"))
    head = commit("Changed")
    thin = git("pack-objects", "--stdout", "--thin", "--revs", data=head + b"\n^" + base + b"\n")
    with PackData("", file=BytesIO(thin), object_format=repo.object_format) as incoming:
        assert any(obj.pack_type_num == 7 for obj in incoming.iter_unpacked())
    repo.object_store.add_thin_pack(BytesIO(thin).read, None)
    target_blob = ObjectID(git("rev-parse", "HEAD:data.txt").strip())
    assert repo.object_store[target_blob].as_raw_string() == path.read_bytes()
    assert len(repo.get_pending_changes()["pack_uploads"]) == 1
    snapshot = dict(repo.object_store.packs_data)
    repo.close()
    reloaded = BlobRepository()
    reloaded.load_from_storage(snapshot, {"refs/heads/main": head})
    assert reloaded.object_store[target_blob].as_raw_string() == path.read_bytes()
    reloaded.close()
