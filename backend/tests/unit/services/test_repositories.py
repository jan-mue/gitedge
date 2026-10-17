from __future__ import annotations

import os
import stat
import tempfile
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, cast

import pytest
from dulwich.object_format import DEFAULT_OBJECT_FORMAT
from dulwich.objects import Blob, Commit, ObjectID, ShaFile, Tree
from dulwich.pack import write_pack
from dulwich.refs import SYMREF, Ref
from fastapi import HTTPException

import app.clients.git.dulwich.repositories as repository_module
from app.clients.git.dulwich.blob_backend import BlobBackend
from app.entities.users import User
from app.exceptions import RepositoryNotFoundError
from app.schemas.repositories import FileContent, RepositoryUpdate, TreeListing
from app.services.repositories import RepositoryService, ensure_repository
from app.types import PackContents
from app.utils.cache_headers import (
    CACHE_CONTROL_IMMUTABLE,
    CACHE_CONTROL_PRIVATE,
    CACHE_CONTROL_REVALIDATE,
    is_commit_sha,
)
from tests.unit.utils.fakes import (
    FakeBlobStorageClient,
    FakeCacheClient,
    FakeOrganizationStore,
    FakeRedisClient,
    FakeRepositoryStore,
    FakeStarStore,
    FakeUserStore,
)
from tests.unit.utils.git import build_repository_service, git_client

if TYPE_CHECKING:
    from pytest_mock import MockerFixture

    from app.clients.git.dulwich.blob_repository import BlobRepository

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


def _populate_path_history(backend: BlobBackend) -> dict[str, Commit]:
    objects: list[ShaFile] = []

    def snapshot(readme: bytes, code: bytes, parents: list[ObjectID], message: str, timestamp: int) -> Commit:
        readme_blob = Blob.from_string(readme)
        code_blob = Blob.from_string(code)
        src_tree = _write_tree({"main.py": (stat.S_IFREG | 0o644, code_blob.id)})
        tree = _write_tree({"README.md": (stat.S_IFREG | 0o644, readme_blob.id), "src": (stat.S_IFDIR, src_tree.id)})
        commit = _make_commit(tree.id, message)
        commit.parents = parents
        commit.commit_time = commit.author_time = timestamp
        objects.extend([readme_blob, code_blob, src_tree, tree, commit])
        return commit

    initial = snapshot(b"Original README", b"original code", [], "Initial files", 1_700_000_000)
    code = snapshot(b"Original README", b"updated code", [initial.id], "Update source", 1_700_001_000)
    docs = snapshot(b"Updated README", b"updated code", [code.id], "Update documentation", 1_700_002_000)
    feature = snapshot(b"Original README", b"feature code", [initial.id], "Implement feature", 1_700_003_000)
    merge = snapshot(b"Updated README", b"feature code", [docs.id, feature.id], "Merge feature", 1_700_004_000)
    repo = _load_repository(backend, "owner/repo.git", list({obj.id: obj for obj in objects}.values()), docs.id)
    repo.refs[Ref(b"refs/heads/merged")] = merge.id
    repo.refs[Ref(b"refs/tags/v1")] = initial.id
    return {"initial": initial, "code": code, "docs": docs, "feature": feature, "merge": merge}


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
    return build_repository_service(
        BlobBackend(), FakeBlobStorageClient(), FakeRedisClient(), FakeCacheClient(), repository_store, FakeStarStore()
    )


async def test_ensure_repository() -> None:
    _, _, store = _stores()

    repository = await ensure_repository(store, OWNER, REPO)
    assert repository.name == REPO
    assert repository.owner_id == OWNER_ID
    assert await ensure_repository(store, OWNER, REPO) is repository


async def test_activity_history_deduplicates_branches_and_excludes_merge_diffs(service: RepositoryService) -> None:
    timestamp = int(datetime.now(UTC).timestamp())
    objects: list[ShaFile] = []

    def commit_file(content: bytes, parents: list[ObjectID], message: str) -> Commit:
        blob = Blob.from_string(content)
        tree = _write_tree({"file.txt": (stat.S_IFREG | 0o644, blob.id)})
        commit = _make_commit(tree.id, message)
        commit.parents = parents
        commit.author_time = commit.commit_time = timestamp
        objects.extend([blob, tree, commit])
        return commit

    root = commit_file(b"one\n+++ tricky\n", [], "Initial")
    main = commit_file(b"one\nnew\n", [root.id], "Main")
    feature = commit_file(b"feature\n", [root.id], "Feature")
    merged = commit_file(b"one\nnew\nfeature\n", [main.id, feature.id], "Merge")
    branch = commit_file(b"one\n+++ tricky\nside\n", [root.id], "Unmerged")
    repo = _load_repository(git_client(service).backend, "owner/repo.git", objects, merged.id)
    repo.refs[Ref(b"refs/heads/feature")] = feature.id
    repo.refs[Ref(b"refs/heads/side")] = branch.id
    repo.refs[Ref(b"refs/heads/side-copy")] = branch.id

    history = await service.activity_history(OWNER, REPO)
    assert history.default_branch == "main"
    assert len(history.commits) == 5
    by_sha = {commit.sha: commit for commit in history.commits}
    assert by_sha[root.id.decode()].additions == 2
    assert by_sha[main.id.decode()].additions == 1
    assert by_sha[main.id.decode()].deletions == 1
    assert by_sha[feature.id.decode()].deletions == 2
    assert by_sha[merged.id.decode()].is_merge
    assert by_sha[merged.id.decode()].additions == 0
    assert by_sha[merged.id.decode()].files == []
    assert not by_sha[branch.id.decode()].is_default
    assert by_sha[branch.id.decode()].files == ["file.txt"]
    assert (await service.activity_history(OWNER, REPO)) == history
    assert (await service.get_statistics(OWNER, REPO, "main")).commit_count == 4


async def test_create_repository(service: RepositoryService) -> None:
    repository = await service.create_repository(OWNER, "newrepo")

    assert repository.name == "newrepo"
    assert repository.owner == OWNER
    assert git_client(service).backend.repository_exists("owner/newrepo.git")

    result = await service.list_repositories()
    assert result.count == 1


async def test_list_repositories(service: RepositoryService) -> None:
    _populate_repo(git_client(service).backend)
    await service.save_changes(OWNER, REPO)
    assert service.repository_store is not None
    await ensure_repository(service.repository_store, OWNER, REPO)

    result = await service.list_repositories()
    assert result.count == 1
    assert result.data[0].name == REPO
    assert result.data[0].owner == OWNER


async def test_get_repository(service: RepositoryService) -> None:
    _populate_repo(git_client(service).backend)
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
        await git_client(service).load_repository(OWNER, "missing")


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
    assert git_client(service).backend.repository_exists("owner/new.git")


async def test_ensure_loaded_keeps_existing_repository(service: RepositoryService) -> None:
    commit_id = _populate_repo(git_client(service).backend)
    await service.ensure_loaded(OWNER, REPO)

    repo = git_client(service).backend.open_repository("owner/repo.git")
    assert repo.refs.read_loose_ref(Ref(b"refs/heads/main")) == commit_id


async def test_save_changes_noop_for_unknown_repository(service: RepositoryService) -> None:
    await service.save_changes(OWNER, "unknown")
    result = await service.list_repositories()
    assert result.count == 0


async def test_get_tree(service: RepositoryService) -> None:
    _populate_repo(git_client(service).backend)

    listing = await service.get_tree(OWNER, REPO, "main", "")
    assert [entry.name for entry in listing.entries] == ["src", "README.md"]
    assert listing.entries[0].type == "tree"
    assert listing.entries[1].type == "blob"
    assert listing.entries[1].size == len(b"# Title\n\nHello world\n")


async def test_get_tree_subdirectory(service: RepositoryService) -> None:
    _populate_repo(git_client(service).backend)

    listing = await service.get_tree(OWNER, REPO, "main", "src")
    assert [entry.name for entry in listing.entries] == ["main.py"]
    assert listing.entries[0].path == "src/main.py"


async def test_source_last_commits_are_specific_to_files_and_directories(service: RepositoryService) -> None:
    commits = _populate_path_history(git_client(service).backend)

    listing = await service.get_tree(OWNER, REPO, "main", "")
    by_name = {entry.name: entry for entry in listing.entries}
    assert by_name["src"].last_commit is not None
    assert by_name["src"].last_commit.sha == commits["code"].id.decode()
    assert by_name["README.md"].last_commit is not None
    assert by_name["README.md"].last_commit.sha == commits["docs"].id.decode()

    nested = await service.get_tree(OWNER, REPO, "main", "src")
    file = await service.get_blob(OWNER, REPO, "main", "src/main.py")
    assert file.last_commit == nested.entries[0].last_commit == by_name["src"].last_commit
    assert file.last_commit is not None
    assert file.last_commit.message == "Update source"
    assert file.last_commit.timestamp == commits["code"].author_time


@pytest.mark.parametrize("ref", ["refs/tags/v1", "initial"])
async def test_source_last_commits_follow_the_selected_revision(service: RepositoryService, ref: str) -> None:
    commits = _populate_path_history(git_client(service).backend)
    revision = commits["initial"].id.decode() if ref == "initial" else ref

    listing = await service.get_tree(OWNER, REPO, revision, "")
    assert all(
        entry.last_commit and entry.last_commit.sha == commits["initial"].id.decode() for entry in listing.entries
    )
    file = await service.get_blob(OWNER, REPO, revision, "src/main.py")
    assert file.last_commit is not None
    assert file.last_commit.sha == commits["initial"].id.decode()
    assert file.content == "original code"


async def test_source_last_commits_follow_unchanged_merge_parents(service: RepositoryService) -> None:
    commits = _populate_path_history(git_client(service).backend)

    listing = await service.get_tree(OWNER, REPO, "merged", "")
    by_name = {entry.name: entry for entry in listing.entries}
    assert by_name["src"].last_commit is not None
    assert by_name["src"].last_commit.sha == commits["feature"].id.decode()
    assert by_name["README.md"].last_commit is not None
    assert by_name["README.md"].last_commit.sha == commits["docs"].id.decode()
    file = await service.get_blob(OWNER, REPO, "merged", "src/main.py")
    assert file.last_commit == by_name["src"].last_commit


async def test_get_tree_unknown_ref(service: RepositoryService) -> None:
    _populate_repo(git_client(service).backend)

    with pytest.raises(HTTPException):
        await service.get_tree(OWNER, REPO, "missing", "")


async def test_get_blob(service: RepositoryService) -> None:
    _populate_repo(git_client(service).backend)

    file = await service.get_blob(OWNER, REPO, "main", "src/main.py")
    assert file.name == "main.py"
    assert file.language == "Python"
    assert 'print("hi")' in file.content
    assert "highlight" in file.highlighted_html
    assert file.line_count == 2


async def test_get_blob_binary(service: RepositoryService) -> None:
    _populate_single_file(git_client(service).backend, "owner/binary.git", "data.bin", b"\xff\xfe\x00")

    file = await service.get_blob(OWNER, "binary", "main", "data.bin")
    assert file.content == "(binary file)"


async def test_get_blob_requires_file_path(service: RepositoryService) -> None:
    with pytest.raises(HTTPException):
        await service.get_blob(OWNER, REPO, "main", "")


async def test_get_blob_not_a_file(service: RepositoryService) -> None:
    _populate_repo(git_client(service).backend)

    with pytest.raises(HTTPException):
        await service.get_blob(OWNER, REPO, "main", "src")


async def test_get_blob_not_found(service: RepositoryService) -> None:
    _populate_repo(git_client(service).backend)

    with pytest.raises(HTTPException):
        await service.get_blob(OWNER, REPO, "main", "missing.py")


async def test_get_info(service: RepositoryService) -> None:
    _populate_repo(git_client(service).backend)

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
    _populate_repo(git_client(service).backend)

    info = await service.get_info(OWNER, REPO, "missing")
    assert info.last_commit is None


async def test_get_readme(service: RepositoryService) -> None:
    _populate_repo(git_client(service).backend)

    readme = await service.get_readme(OWNER, REPO, "main", "")
    assert readme.filename == "README.md"
    assert "<h1>" in readme.html
    assert "Title" in readme.html


async def test_get_readme_not_found(service: RepositoryService) -> None:
    _populate_single_file(git_client(service).backend, "owner/noreadme.git", "file.txt", b"content")

    with pytest.raises(HTTPException):
        await service.get_readme(OWNER, "noreadme", "main", "")


async def test_list_branches(service: RepositoryService) -> None:
    _populate_repo(git_client(service).backend)

    branches = await service.list_branches(OWNER, REPO)
    assert len(branches) == 1
    assert branches[0].name == "main"
    assert branches[0].is_default is True


async def test_list_commits(service: RepositoryService) -> None:
    commit_id = _populate_repo(git_client(service).backend)

    commits = await service.list_commits(OWNER, REPO, "main")
    assert commits.count == 1
    assert commits.ref == "main"
    assert commits.data[0].sha == commit_id.decode()
    assert commits.data[0].message == "Initial commit"
    assert commits.data[0].author == "Test User"


async def test_list_commits_missing_ref(service: RepositoryService) -> None:
    _populate_repo(git_client(service).backend)

    commits = await service.list_commits(OWNER, REPO, "missing")
    assert commits.count == 0
    assert commits.data == []


async def test_get_commit(service: RepositoryService) -> None:
    commit_id = _populate_repo(git_client(service).backend)

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
    _populate_repo(git_client(service).backend)

    with pytest.raises(HTTPException):
        await service.get_commit(OWNER, REPO, "0" * 40)


def test_is_commit_sha() -> None:
    assert is_commit_sha("a" * 40)
    assert not is_commit_sha("main")


async def test_get_tree_is_cached(service: RepositoryService, mocker: MockerFixture) -> None:
    _populate_repo(git_client(service).backend)
    load = mocker.spy(git_client(service), "load_repository")

    first = await service.get_tree(OWNER, REPO, "main", "")
    second = await service.get_tree(OWNER, REPO, "main", "")

    assert second == first
    assert load.await_count == 1


async def test_save_changes_invalidates_cache(service: RepositoryService) -> None:
    cache = cast(FakeCacheClient, service.cache_client)
    _populate_repo(git_client(service).backend)
    await service.get_tree(OWNER, REPO, "main", "")
    group = f"repo:{OWNER}/{REPO}"
    assert any(entry[0] == group for entry in cache.values)

    _populate_repo(git_client(service).backend)
    await service.save_changes(OWNER, REPO)

    assert not any(entry[0] == group for entry in cache.values)


async def test_cache_headers_public_revalidate(service: RepositoryService) -> None:
    await ensure_repository(service.repository_store, OWNER, REPO)

    headers = await service.cache_headers(OWNER, REPO, immutable=False)

    assert headers["Cache-Control"] == CACHE_CONTROL_REVALIDATE


async def test_cache_headers_immutable(service: RepositoryService) -> None:
    await ensure_repository(service.repository_store, OWNER, REPO)

    headers = await service.cache_headers(OWNER, REPO, immutable=True)

    assert headers["Cache-Control"] == CACHE_CONTROL_IMMUTABLE


async def test_cache_headers_private(service: RepositoryService) -> None:
    repository = await ensure_repository(service.repository_store, OWNER, REPO)
    repository.is_private = True

    headers = await service.cache_headers(OWNER, REPO, immutable=True)

    assert headers["Cache-Control"] == CACHE_CONTROL_PRIVATE


async def test_statistics_file_index_and_raw(service: RepositoryService) -> None:
    sha = _populate_repo(git_client(service).backend)
    stats = await service.get_statistics(OWNER, REPO, "main")
    assert stats.commit_count == 1
    assert stats.size == len(b"# Title\n\nHello world\n") + len(b'def main():\n    print("hi")\n')
    assert {language.name for language in stats.languages} == {"Python"}
    assert sum(language.percentage for language in stats.languages) == pytest.approx(100, abs=0.02)
    assert (await service.get_file_index(OWNER, REPO, sha.decode())).paths == ["README.md", "src/main.py"]
    assert await service.get_raw(OWNER, REPO, "main", "README.md") == b"# Title\n\nHello world\n"
    assert isinstance(await service.get_source(OWNER, REPO, "main", "src"), TreeListing)
    assert isinstance(await service.get_source(OWNER, REPO, "main", "src/main.py"), FileContent)


async def test_statistics_binary_and_empty_files(service: RepositoryService) -> None:
    _populate_single_file(git_client(service).backend, "owner/repo.git", "image.png", b"\x89PNG\0\xff")
    result = await service.get_statistics(OWNER, REPO, "main")
    assert result.size == 6
    assert result.languages == []
    await service.create_repository(OWNER, "empty")
    assert (await service.get_statistics(OWNER, "empty", "HEAD")).commit_count == 0
    assert (await service.get_file_index(OWNER, "empty", "HEAD")).paths == []


async def test_statistics_groups_source_bytes_and_excludes_non_source(service: RepositoryService) -> None:
    contents = {
        "main.ts": b"const answer = 42;\n",
        "view.tsx": b"export const View = () => <p>Hello</p>;\n",
        "main.py": b"print('hello')\n",
        "README.md": b"# Documentation\n" * 100,
        "package.json": b'{"name":"example"}',
        "bun.lock": b'{"lockfileVersion":1}',
        "app.min.js": b"const answer=42;",
    }
    blobs = {path: Blob.from_string(content) for path, content in contents.items()}
    tree = _write_tree({path: (stat.S_IFREG | 0o644, blob.id) for path, blob in blobs.items()})
    commit = _make_commit(tree.id)
    _load_repository(git_client(service).backend, "owner/repo.git", [*blobs.values(), tree, commit], commit.id)

    stats = await service.get_statistics(OWNER, REPO, "main")
    source_bytes = len(contents["main.ts"]) + len(contents["view.tsx"]) + len(contents["main.py"])
    assert stats.size == sum(len(content) for content in contents.values())
    assert {language.name: language.size for language in stats.languages} == {
        "TypeScript": len(contents["main.ts"]) + len(contents["view.tsx"]),
        "Python": len(contents["main.py"]),
    }
    for language in stats.languages:
        assert language.percentage == round(language.size / source_bytes * 100, 2)


async def test_statistics_reuses_commit_cache_across_refs(service: RepositoryService, mocker: MockerFixture) -> None:
    sha = _populate_repo(git_client(service).backend)
    compute = mocker.spy(repository_module.DulwichGitClient, "_compute_statistics")
    original = await service.get_statistics(OWNER, REPO, "main")
    assert await service.get_statistics(OWNER, REPO, sha.decode()) == original
    assert await service.get_statistics(OWNER, REPO, "HEAD") == original
    assert compute.call_count == 1

    _populate_single_file(git_client(service).backend, "owner/repo.git", "changed.tsx", b"<p>Changed</p>")
    changed = await service.get_statistics(OWNER, REPO, "main")
    assert [language.name for language in changed.languages] == ["TypeScript"]
    assert compute.call_count == 2


async def test_file_index_does_not_load_blob_contents(service: RepositoryService, mocker: MockerFixture) -> None:
    _populate_repo(git_client(service).backend)
    repo = git_client(service).backend.open_repository("owner/repo.git")
    read = mocker.spy(repo.object_store, "get_raw")
    assert (await service.get_file_index(OWNER, REPO, "main")).paths == ["README.md", "src/main.py"]
    blob_ids = {
        Blob.from_string(content).id for content in [b"# Title\n\nHello world\n", b'def main():\n    print("hi")\n']
    }
    assert all(call.args[0] not in blob_ids for call in read.call_args_list)


async def test_blame_tracks_lines_across_commits_and_renames(service: RepositoryService) -> None:
    first_blob = Blob.from_string(b"unchanged\noriginal\n")
    first_tree = _write_tree({"old.txt": (stat.S_IFREG | 0o644, first_blob.id)})
    first = _make_commit(first_tree.id, "Original content")
    rename_tree = _write_tree({"renamed.txt": (stat.S_IFREG | 0o644, first_blob.id)})
    rename = _make_commit(rename_tree.id, "Rename file")
    rename.parents = [first.id]
    second_blob = Blob.from_string(b"unchanged\nchanged\nadded\n")
    second_tree = _write_tree({"renamed.txt": (stat.S_IFREG | 0o644, second_blob.id)})
    second = _make_commit(second_tree.id, "Rename and edit")
    second.parents = [rename.id]
    second.author = b"Second Author <second@example.com>"
    _load_repository(
        git_client(service).backend,
        "owner/repo.git",
        [first_blob, first_tree, first, rename_tree, rename, second_blob, second_tree, second],
        second.id,
    )
    result = await service.get_blame(OWNER, REPO, "main", "renamed.txt")
    assert result.revision == second.id.decode()
    assert [line.content for line in result.lines] == ["unchanged", "changed", "added"]
    assert [line.commit.sha for line in result.lines] == [first.id.decode(), second.id.decode(), second.id.decode()]
    assert result.lines[-1].commit.author == "Second Author"
    historical = await service.get_blame(OWNER, REPO, first.id.decode(), "old.txt")
    assert [line.content for line in historical.lines] == ["unchanged", "original"]
    history = await service.list_commits(OWNER, REPO, "main", file_path="renamed.txt")
    assert history.data[0].sha == second.id.decode()


@pytest.mark.parametrize("data", [b"\0binary", b"\xff", b"x" * (1024 * 1024 + 1)])
async def test_blame_rejects_unrenderable_files(service: RepositoryService, data: bytes) -> None:
    _populate_single_file(git_client(service).backend, "owner/repo.git", "file.txt", data)
    with pytest.raises(HTTPException) as error:
        await service.get_blame(OWNER, REPO, "main", "file.txt")
    assert error.value.status_code in (400, 413)


async def test_blame_empty_and_missing_files(service: RepositoryService) -> None:
    _populate_single_file(git_client(service).backend, "owner/repo.git", "empty.txt", b"")
    assert (await service.get_blame(OWNER, REPO, "main", "empty.txt")).lines == []
    with pytest.raises(HTTPException) as error:
        await service.get_blame(OWNER, REPO, "main", "missing.txt")
    assert error.value.status_code == 404


async def test_settings_rename_preserves_git_and_updates_head(service: RepositoryService) -> None:
    sha = _populate_repo(git_client(service).backend)
    await service.save_changes(OWNER, REPO)
    entity = await ensure_repository(service.repository_store, OWNER, REPO)
    user = entity.owner
    assert isinstance(user, User)
    repo = git_client(service).backend.open_repository("owner/repo.git")
    for basename, pack in _pack([repo.object_store[oid] for oid in repo.object_store]).items():
        await git_client(service).storage.blob.put(f"owner/repo.git/packs/{basename}.pack", pack.pack)
        await git_client(service).storage.blob.put(f"owner/repo.git/packs/{basename}.idx", pack.index)
    repo.refs.set_if_equals(Ref(b"refs/heads/develop"), None, sha)
    await service.save_changes(OWNER, REPO)
    updated = await service.update_repository(
        OWNER, REPO, RepositoryUpdate(name="renamed", description="Updated", default_branch="develop"), user
    )
    assert updated.name == "renamed"
    assert updated.description == "Updated"
    assert updated.default_branch == "develop"
    assert not git_client(service).backend.repository_exists("owner/repo.git")
    assert not await git_client(service).storage.redis.scan_keys("owner/repo.git/refs/*")
    assert not await git_client(service).storage.blob.list_keys("owner/repo.git/")
    assert (await service.get_info(OWNER, "renamed", "HEAD")).default_branch == "develop"
    assert await service.get_raw(OWNER, "renamed", "HEAD", "README.md") == b"# Title\n\nHello world\n"
    with pytest.raises(RepositoryNotFoundError):
        await service.get_repository(OWNER, REPO)


async def test_settings_reject_invalid_branch_or_duplicate_name(service: RepositoryService) -> None:
    _populate_repo(git_client(service).backend)
    entity = await ensure_repository(service.repository_store, OWNER, REPO)
    user = entity.owner
    assert isinstance(user, User)
    await service.create_repository(OWNER, "taken")
    for body, status in [
        (RepositoryUpdate(default_branch="missing"), 400),
        (RepositoryUpdate(default_branch="bad..name"), 400),
        (RepositoryUpdate(name="taken"), 409),
    ]:
        with pytest.raises(HTTPException) as error:
            await service.update_repository(OWNER, REPO, body, user)
        assert error.value.status_code == status
    assert entity.name == REPO
    assert entity.default_branch == "main"


async def test_settings_and_deletion_require_owner(service: RepositoryService) -> None:
    await service.create_repository(OWNER, REPO)
    outsider = User(id=uuid.uuid4(), name="outsider", email="out@example.com", hashed_password="x", is_superuser=False)
    with pytest.raises(HTTPException) as error:
        await service.update_repository(OWNER, REPO, RepositoryUpdate(description="changed"), outsider)
    assert error.value.status_code == 403
    with pytest.raises(HTTPException) as error:
        await service.delete_repository(OWNER, REPO, outsider)
    assert error.value.status_code == 403
    assert git_client(service).backend.repository_exists("owner/repo.git")


async def test_delete_evicts_storage_and_cache_without_deleting_neighbor(service: RepositoryService) -> None:
    _populate_repo(git_client(service).backend)
    await service.save_changes(OWNER, REPO)
    entity = await ensure_repository(service.repository_store, OWNER, REPO)
    user = entity.owner
    assert isinstance(user, User)
    await service.get_statistics(OWNER, REPO, "main")
    await service.create_repository(OWNER, "repo-other")
    await service.delete_repository(OWNER, REPO, user)
    assert not git_client(service).backend.repository_exists("owner/repo.git")
    assert not await git_client(service).storage.redis.scan_keys("owner/repo.git/refs/*")
    assert not await git_client(service).storage.blob.list_keys("owner/repo.git/")
    assert await service.repository_store.find_by_owner_and_name(OWNER, REPO) is None
    assert await service.repository_store.find_by_owner_and_name(OWNER, "repo-other") is not None
    with pytest.raises(HTTPException):
        await service.get_statistics(OWNER, REPO, "main")


async def test_compact_commit_skips_highlighting_and_lazy_files_are_cached(
    service: RepositoryService, mocker: MockerFixture
) -> None:
    commit_id = _populate_repo(git_client(service).backend)
    highlight = mocker.spy(repository_module, "enrich_diff")
    summary = await service.get_commit(OWNER, REPO, commit_id.decode(), include_diff=False)
    assert summary.files
    assert all(not file.diff_loaded and not file.patch and not file.hunks for file in summary.files)
    assert all(file.diff_line_count > 0 for file in summary.files)
    highlight.assert_not_called()
    file = await service.get_diff_file(OWNER, REPO, commit_id.decode(), "src/main.py")
    assert file.diff_loaded
    assert file.language == "Python"
    assert file.hunks
    assert file.diff_line_count > 0
    highlight.assert_called_once()
    assert await service.get_diff_file(OWNER, REPO, commit_id.decode(), "src/main.py") == file
    highlight.assert_called_once()


async def test_lazy_diff_rejects_unchanged_paths_directories_and_missing_revisions(service: RepositoryService) -> None:
    commit_id = _populate_repo(git_client(service).backend).decode()
    for path in ("src/main.py", "missing.py", "src"):
        with pytest.raises(HTTPException) as error:
            await service.get_diff_file(OWNER, REPO, commit_id, path, commit_id)
        assert error.value.status_code == 404
    with pytest.raises(HTTPException) as error:
        await service.get_diff_file(OWNER, REPO, "0" * 40, "src/main.py")
    assert error.value.status_code == 404


async def test_pr_commit_range_excludes_base_ancestors_and_paginates(service: RepositoryService) -> None:
    commits = _populate_path_history(git_client(service).backend)
    first = await service.compare_commits(OWNER, REPO, "main", "merged", limit=1)
    second = await service.compare_commits(OWNER, REPO, "main", "merged", offset=1, limit=1)
    assert first.count == second.count == 2
    assert [item.sha for item in first.data + second.data] == [
        commits["merge"].id.decode(),
        commits["feature"].id.decode(),
    ]
    assert not (await service.compare_commits(OWNER, REPO, "merged", "main")).data
