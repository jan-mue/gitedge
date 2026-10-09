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
from app.exceptions import RepositoryNotFoundError
from app.services.blob_backend import BlobBackend
from app.services.repositories import RepositoryService, ensure_repository
from app.types import PackContents
from tests.unit.utils.fakes import (
    FakeBlobStorageClient,
    FakeOrganizationStore,
    FakeRedisClient,
    FakeRepositoryStore,
    FakeStarStore,
    FakeUserStore,
)

if TYPE_CHECKING:
    from app.services.blob_repository import BlobRepository

OWNER_ID = uuid.uuid4()
OWNER = "owner"
REPO = "repo"


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
    key: str,
    objects: list[ShaFile],
    commit_id: ObjectID,
) -> BlobRepository:
    refs = {"HEAD": SYMREF + b"refs/heads/main", "refs/heads/main": commit_id}
    repo = backend.load_repository_from_data(key, _pack(objects), refs)
    # Mark the branch as a pending change so save_changes persists it.
    repo.refs.set_if_equals(Ref(b"refs/heads/main"), None, commit_id)
    return repo


def _populate_repo(backend: BlobBackend, key: str = "owner/repo.git") -> ObjectID:
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
    _load_repository(backend, key, [readme, main_py, src_tree, root_tree, commit], commit.id)
    return commit.id


def _populate_single_file(backend: BlobBackend, key: str, name: str, data: bytes) -> None:
    blob = Blob.from_string(data)
    tree = _write_tree({name: (stat.S_IFREG | 0o644, blob.id)})
    commit = _make_commit(tree.id)
    _load_repository(backend, key, [blob, tree, commit], commit.id)


def _stores() -> tuple[FakeUserStore, FakeOrganizationStore, FakeRepositoryStore]:
    users = FakeUserStore()
    owner = User(name=OWNER, lower_name=OWNER.lower(), email="owner@example.com", hashed_password="x")
    owner.id = OWNER_ID
    users.persist(owner)
    organizations = FakeOrganizationStore()
    return users, organizations, FakeRepositoryStore(users, organizations)


@pytest.fixture
def service() -> RepositoryService:
    _, _, repository_store = _stores()
    return RepositoryService(
        BlobBackend(), FakeBlobStorageClient(), FakeRedisClient(), repository_store, FakeStarStore()
    )


async def test_ensure_repository() -> None:
    _, _, store = _stores()

    repository = await ensure_repository(store, OWNER, REPO)
    assert repository.name == REPO
    assert repository.owner_id == OWNER_ID
    assert await ensure_repository(store, OWNER, REPO) is repository


async def test_create_repository(service: RepositoryService) -> None:
    repository = await service.create_repository(OWNER, "newrepo")

    assert repository.name == "newrepo"
    assert repository.owner == OWNER
    assert service.backend.repository_exists("owner/newrepo.git")

    result = await service.list_repositories()
    assert result.count == 1


async def test_list_repositories(service: RepositoryService) -> None:
    _populate_repo(service.backend)
    await service.save_changes(OWNER, REPO)
    assert service.repository_store is not None
    await ensure_repository(service.repository_store, OWNER, REPO)

    result = await service.list_repositories()
    assert result.count == 1
    assert result.data[0].name == REPO
    assert result.data[0].owner == OWNER


async def test_get_repository(service: RepositoryService) -> None:
    _populate_repo(service.backend)
    await service.save_changes(OWNER, REPO)
    assert service.repository_store is not None
    await ensure_repository(service.repository_store, OWNER, REPO)

    repository = await service.get_repository(OWNER, REPO)
    assert repository.owner == OWNER
    assert repository.name == REPO


async def test_get_repository_not_found(service: RepositoryService) -> None:
    with pytest.raises(RepositoryNotFoundError):
        await service.get_repository(OWNER, "missing")


async def test_load_repository_not_found(service: RepositoryService) -> None:
    with pytest.raises(HTTPException):
        await service.load_repository(OWNER, "missing")


async def test_load_repository_empty_when_row_exists(service: RepositoryService) -> None:
    assert service.repository_store is not None
    await ensure_repository(service.repository_store, OWNER, "empty")

    info = await service.get_info(OWNER, "empty", "main")
    assert info.branch_count == 0
    assert info.tag_count == 0
    assert info.default_branch == "main"
    assert info.last_commit is None


async def test_ensure_loaded_creates_repository(service: RepositoryService) -> None:
    await service.ensure_loaded(OWNER, "new")
    assert service.backend.repository_exists("owner/new.git")


async def test_ensure_loaded_keeps_existing_repository(service: RepositoryService) -> None:
    commit_id = _populate_repo(service.backend)
    await service.ensure_loaded(OWNER, REPO)

    repo = service.backend.open_repository("owner/repo.git")
    assert repo.refs.read_loose_ref(Ref(b"refs/heads/main")) == commit_id


async def test_save_changes_noop_for_unknown_repository(service: RepositoryService) -> None:
    await service.save_changes(OWNER, "unknown")
    result = await service.list_repositories()
    assert result.count == 0


async def test_get_tree(service: RepositoryService) -> None:
    _populate_repo(service.backend)

    listing = await service.get_tree(OWNER, REPO, "main", "")
    assert [entry.name for entry in listing.entries] == ["src", "README.md"]
    assert listing.entries[0].type == "tree"
    assert listing.entries[1].type == "blob"
    assert listing.entries[1].size == len(b"# Title\n\nHello world\n")


async def test_get_tree_subdirectory(service: RepositoryService) -> None:
    _populate_repo(service.backend)

    listing = await service.get_tree(OWNER, REPO, "main", "src")
    assert [entry.name for entry in listing.entries] == ["main.py"]
    assert listing.entries[0].path == "src/main.py"


async def test_get_tree_unknown_ref(service: RepositoryService) -> None:
    _populate_repo(service.backend)

    with pytest.raises(HTTPException):
        await service.get_tree(OWNER, REPO, "missing", "")


async def test_get_blob(service: RepositoryService) -> None:
    _populate_repo(service.backend)

    file = await service.get_blob(OWNER, REPO, "main", "src/main.py")
    assert file.name == "main.py"
    assert file.language == "Python"
    assert 'print("hi")' in file.content
    assert "highlight" in file.highlighted_html
    assert file.line_count == 2


async def test_get_blob_binary(service: RepositoryService) -> None:
    _populate_single_file(service.backend, "owner/binary.git", "data.bin", b"\xff\xfe\x00")

    file = await service.get_blob(OWNER, "binary", "main", "data.bin")
    assert file.content == "(binary file)"


async def test_get_blob_requires_file_path(service: RepositoryService) -> None:
    with pytest.raises(HTTPException):
        await service.get_blob(OWNER, REPO, "main", "")


async def test_get_blob_not_a_file(service: RepositoryService) -> None:
    _populate_repo(service.backend)

    with pytest.raises(HTTPException):
        await service.get_blob(OWNER, REPO, "main", "src")


async def test_get_blob_not_found(service: RepositoryService) -> None:
    _populate_repo(service.backend)

    with pytest.raises(HTTPException):
        await service.get_blob(OWNER, REPO, "main", "missing.py")


async def test_get_info(service: RepositoryService) -> None:
    _populate_repo(service.backend)

    info = await service.get_info(OWNER, REPO, "main")
    assert info.name == REPO
    assert info.owner == OWNER
    assert info.default_branch == "main"
    assert info.branch_count == 1
    assert info.tag_count == 0
    assert info.last_commit is not None
    assert info.last_commit.message == "Initial commit"
    assert info.last_commit.author == "Test User"


async def test_get_info_missing_ref(service: RepositoryService) -> None:
    _populate_repo(service.backend)

    info = await service.get_info(OWNER, REPO, "missing")
    assert info.last_commit is None


async def test_get_readme(service: RepositoryService) -> None:
    _populate_repo(service.backend)

    readme = await service.get_readme(OWNER, REPO, "main", "")
    assert readme.filename == "README.md"
    assert "<h1>" in readme.html
    assert "Title" in readme.html


async def test_get_readme_not_found(service: RepositoryService) -> None:
    _populate_single_file(service.backend, "owner/noreadme.git", "file.txt", b"content")

    with pytest.raises(HTTPException):
        await service.get_readme(OWNER, "noreadme", "main", "")


async def test_list_branches(service: RepositoryService) -> None:
    _populate_repo(service.backend)

    branches = await service.list_branches(OWNER, REPO)
    assert len(branches) == 1
    assert branches[0].name == "main"
    assert branches[0].is_default is True


async def test_list_commits(service: RepositoryService) -> None:
    commit_id = _populate_repo(service.backend)

    commits = await service.list_commits(OWNER, REPO, "main")
    assert commits.count == 1
    assert commits.ref == "main"
    assert commits.data[0].sha == commit_id.decode()
    assert commits.data[0].message == "Initial commit"
    assert commits.data[0].author == "Test User"


async def test_list_commits_missing_ref(service: RepositoryService) -> None:
    _populate_repo(service.backend)

    commits = await service.list_commits(OWNER, REPO, "missing")
    assert commits.count == 0
    assert commits.data == []


async def test_get_commit(service: RepositoryService) -> None:
    commit_id = _populate_repo(service.backend)

    detail = await service.get_commit(OWNER, REPO, commit_id.decode())
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
        await service.get_commit(OWNER, REPO, "0" * 40)
