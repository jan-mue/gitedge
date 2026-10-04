from __future__ import annotations

import os
import stat
import tempfile
import uuid
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from dulwich.object_format import DEFAULT_OBJECT_FORMAT
from dulwich.objects import Blob, Commit, ObjectID, ShaFile, Tree
from dulwich.pack import write_pack
from dulwich.refs import SYMREF, Ref
from fastapi import HTTPException

from app.entities.users import User
from app.services.blob_backend import BlobBackend
from app.services.repositories import (
    RepositoryService,
    ensure_repository,
    normalize_repo_path,
    repository_name_from_path,
)
from app.types import PackContents
from tests.unit.utils.fakes import FakeBlobStorageClient, FakeRedisClient, FakeRepositoryStore

if TYPE_CHECKING:
    from app.services.blob_repository import BlobRepository


def _pack(objects: list[ShaFile]) -> dict[str, PackContents]:
    with tempfile.TemporaryDirectory() as tmp:
        basename = os.path.join(tmp, "pack")
        write_pack(basename, objects, DEFAULT_OBJECT_FORMAT)
        return {
            "pack": PackContents(
                pack=Path(basename + ".pack").read_bytes(),
                index=Path(basename + ".idx").read_bytes(),
            )
        }


def _write_tree(entries: dict[str, tuple[int, ObjectID]]) -> Tree:
    tree = Tree()
    for name, (mode, sha) in entries.items():
        tree.add(name.encode(), mode, sha)
    return tree


def _make_commit(tree_id: ObjectID, message: str = "Initial commit") -> Commit:
    commit = Commit()
    commit.tree = tree_id
    commit.author = commit.committer = b"Test User <test@example.com>"
    commit.commit_time = commit.author_time = 1_700_000_000
    commit.commit_timezone = commit.author_timezone = 0
    commit.message = message.encode()
    return commit


def _load_repository(
    backend: BlobBackend,
    path: str,
    objects: list[ShaFile],
    commit_id: ObjectID,
) -> BlobRepository:
    refs = {"HEAD": SYMREF + b"refs/heads/main", "refs/heads/main": commit_id}
    repo = backend.load_repository_from_data(path, _pack(objects), refs)
    # Mark the branch as a pending change so save_changes persists it.
    repo.refs.set_if_equals(Ref(b"refs/heads/main"), None, commit_id)
    return repo


def _populate_repo(backend: BlobBackend, path: str = "owner/repo.git") -> ObjectID:
    readme = Blob.from_string(b"# Title\n\nHello world\n")
    main_py = Blob.from_string(b'def main():\n    print("hi")\n')
    src_tree = _write_tree({"main.py": (stat.S_IFREG | 0o644, main_py.id)})
    root_tree = _write_tree(
        {
            "README.md": (stat.S_IFREG | 0o644, readme.id),
            "src": (stat.S_IFDIR, src_tree.id),
        }
    )
    commit = _make_commit(root_tree.id)
    _load_repository(backend, path, [readme, main_py, src_tree, root_tree, commit], commit.id)
    return commit.id


def _populate_single_file(backend: BlobBackend, path: str, name: str, data: bytes) -> None:
    blob = Blob.from_string(data)
    tree = _write_tree({name: (stat.S_IFREG | 0o644, blob.id)})
    commit = _make_commit(tree.id)
    _load_repository(backend, path, [blob, tree, commit], commit.id)


@pytest.fixture
def service() -> RepositoryService:
    return RepositoryService(BlobBackend(), FakeBlobStorageClient(), FakeRedisClient())


def test_normalize_repo_path() -> None:
    assert normalize_repo_path("/owner/repo") == "owner/repo.git"
    assert normalize_repo_path("owner/repo.git") == "owner/repo.git"


def test_repository_name_from_path() -> None:
    assert repository_name_from_path("owner/repo.git") == "repo"
    assert repository_name_from_path("repo") == "repo"


async def test_ensure_repository() -> None:
    store = FakeRepositoryStore()
    user = User(email="owner@example.com", hashed_password="x")
    user.id = uuid.uuid4()

    repository = await ensure_repository(store, "owner/repo", user)
    assert repository.name == "repo"
    assert repository.path == "owner/repo.git"
    assert repository.owner_id == user.id
    assert await ensure_repository(store, "owner/repo", user) is repository


async def test_create_repository(service: RepositoryService) -> None:
    repository = await service.create_repository("owner", "newrepo")

    assert repository.name == "newrepo"
    assert repository.path == "owner/newrepo.git"
    assert service.backend.repository_exists("owner/newrepo.git")

    result = await service.list_repositories()
    assert result.count == 1


async def test_list_repositories(service: RepositoryService) -> None:
    _populate_repo(service.backend)
    await service.save_changes("owner/repo.git")

    result = await service.list_repositories()
    assert result.count == 1
    assert result.data[0].name == "repo"
    assert result.data[0].path == "owner/repo.git"


async def test_get_repository(service: RepositoryService) -> None:
    _populate_repo(service.backend)
    await service.save_changes("owner/repo.git")

    repository = await service.get_repository("owner/repo")
    assert repository.path == "owner/repo.git"


async def test_get_repository_not_found(service: RepositoryService) -> None:
    with pytest.raises(HTTPException):
        await service.get_repository("owner/missing")


async def test_load_repository_not_found(service: RepositoryService) -> None:
    with pytest.raises(HTTPException):
        await service.load_repository("owner/missing")


async def test_ensure_loaded_creates_repository(service: RepositoryService) -> None:
    await service.ensure_loaded("owner/new.git")
    assert service.backend.repository_exists("owner/new.git")


async def test_ensure_loaded_keeps_existing_repository(service: RepositoryService) -> None:
    commit_id = _populate_repo(service.backend)
    await service.ensure_loaded("owner/repo.git")

    repo = service.backend.open_repository("owner/repo.git")
    assert repo.refs.read_loose_ref(Ref(b"refs/heads/main")) == commit_id


async def test_save_changes_noop_for_unknown_repository(service: RepositoryService) -> None:
    await service.save_changes("owner/unknown.git")
    result = await service.list_repositories()
    assert result.count == 0


async def test_get_tree(service: RepositoryService) -> None:
    _populate_repo(service.backend)

    listing = await service.get_tree("owner/repo.git", "main", "")
    assert [entry.name for entry in listing.entries] == ["src", "README.md"]
    assert listing.entries[0].type == "tree"
    assert listing.entries[1].type == "blob"
    assert listing.entries[1].size == len(b"# Title\n\nHello world\n")


async def test_get_tree_subdirectory(service: RepositoryService) -> None:
    _populate_repo(service.backend)

    listing = await service.get_tree("owner/repo.git", "main", "src")
    assert [entry.name for entry in listing.entries] == ["main.py"]
    assert listing.entries[0].path == "src/main.py"


async def test_get_tree_unknown_ref(service: RepositoryService) -> None:
    _populate_repo(service.backend)

    with pytest.raises(HTTPException):
        await service.get_tree("owner/repo.git", "missing", "")


async def test_get_blob(service: RepositoryService) -> None:
    _populate_repo(service.backend)

    file = await service.get_blob("owner/repo.git", "main", "src/main.py")
    assert file.name == "main.py"
    assert file.language == "Python"
    assert 'print("hi")' in file.content
    assert "highlight" in file.highlighted_html
    assert file.line_count == 2


async def test_get_blob_binary(service: RepositoryService) -> None:
    _populate_single_file(service.backend, "owner/binary.git", "data.bin", b"\xff\xfe\x00")

    file = await service.get_blob("owner/binary.git", "main", "data.bin")
    assert file.content == "(binary file)"


async def test_get_blob_requires_file_path(service: RepositoryService) -> None:
    with pytest.raises(HTTPException):
        await service.get_blob("owner/repo.git", "main", "")


async def test_get_blob_not_a_file(service: RepositoryService) -> None:
    _populate_repo(service.backend)

    with pytest.raises(HTTPException):
        await service.get_blob("owner/repo.git", "main", "src")


async def test_get_blob_not_found(service: RepositoryService) -> None:
    _populate_repo(service.backend)

    with pytest.raises(HTTPException):
        await service.get_blob("owner/repo.git", "main", "missing.py")


async def test_get_info(service: RepositoryService) -> None:
    _populate_repo(service.backend)

    info = await service.get_info("owner/repo", "main")
    assert info.name == "repo"
    assert info.path == "owner/repo.git"
    assert info.default_branch == "main"
    assert info.branch_count == 1
    assert info.tag_count == 0
    assert info.last_commit is not None
    assert info.last_commit.message == "Initial commit"
    assert info.last_commit.author == "Test User"


async def test_get_info_missing_ref(service: RepositoryService) -> None:
    _populate_repo(service.backend)

    info = await service.get_info("owner/repo", "missing")
    assert info.last_commit is None


async def test_get_readme(service: RepositoryService) -> None:
    _populate_repo(service.backend)

    readme = await service.get_readme("owner/repo.git", "main", "")
    assert readme.filename == "README.md"
    assert "<h1>" in readme.html
    assert "Title" in readme.html


async def test_get_readme_not_found(service: RepositoryService) -> None:
    _populate_single_file(service.backend, "owner/noreadme.git", "file.txt", b"content")

    with pytest.raises(HTTPException):
        await service.get_readme("owner/noreadme.git", "main", "")


async def test_list_branches(service: RepositoryService) -> None:
    _populate_repo(service.backend)

    branches = await service.list_branches("owner/repo.git")
    assert len(branches) == 1
    assert branches[0].name == "main"
    assert branches[0].is_default is True


async def test_list_commits(service: RepositoryService) -> None:
    commit_id = _populate_repo(service.backend)

    commits = await service.list_commits("owner/repo.git", "main")
    assert commits.count == 1
    assert commits.ref == "main"
    assert commits.data[0].sha == commit_id.decode()
    assert commits.data[0].message == "Initial commit"
    assert commits.data[0].author == "Test User"


async def test_list_commits_missing_ref(service: RepositoryService) -> None:
    _populate_repo(service.backend)

    commits = await service.list_commits("owner/repo.git", "missing")
    assert commits.count == 0
    assert commits.data == []


async def test_get_commit(service: RepositoryService) -> None:
    commit_id = _populate_repo(service.backend)

    detail = await service.get_commit("owner/repo.git", commit_id.decode())
    assert detail.sha == commit_id.decode()
    assert detail.message == "Initial commit"
    assert detail.author == "Test User"
    assert detail.parents == []
    assert {file.path for file in detail.files} == {"README.md", "src/main.py"}
    assert detail.additions > 0
    assert all(file.change_type == "add" for file in detail.files)
    assert any(file.patch.startswith("diff --git") for file in detail.files)


async def test_get_commit_not_found(service: RepositoryService) -> None:
    _populate_repo(service.backend)

    with pytest.raises(HTTPException):
        await service.get_commit("owner/repo.git", "0" * 40)
