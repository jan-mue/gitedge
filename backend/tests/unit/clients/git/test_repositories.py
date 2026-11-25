"""Import real Git bundles into in-memory persistence without replacing protected refs."""

import io
from dataclasses import dataclass
from typing import TYPE_CHECKING

import pytest
from dulwich.bundle import create_bundle_from_repo, read_bundle, write_bundle
from dulwich.objects import Blob, Commit, ObjectID, Tree
from dulwich.refs import Ref

from app.clients.git.blob_backend import BlobBackend
from app.exceptions import ConflictError, InvalidInputError
from tests.unit.utils.git import build_repository_service, seed_merge_repository

if TYPE_CHECKING:
    from pytest_mock import MockerFixture

    from app.clients.git.repositories import GitClient
    from tests.unit.utils.fakes import FakeStores


BRANCH = "agents/conversation"


@dataclass
class Publication:
    git: GitClient
    owner: str
    base: str
    head: str
    contents: bytes


@pytest.fixture
async def publication(fake_stores: FakeStores) -> Publication:
    owner = next(iter(fake_stores.users.items.values())).name
    base, _, _ = seed_merge_repository(fake_stores, owner, "repo")
    git = build_repository_service(
        BlobBackend(), fake_stores.blob, fake_stores.redis, fake_stores.cache, fake_stores.repository, fake_stores.stars
    ).git
    source = await git.load_repository(owner, "repo")
    blob = Blob.from_string(b"Agent changed this README.\n")
    tree = Tree()
    tree.add(b"README.md", 0o100644, blob.id)
    commit = Commit()
    commit.tree = tree.id
    commit.parents = [ObjectID(base.encode())]
    commit.author = commit.committer = b"Agent <agent@example.com>"
    commit.author_time = commit.commit_time = 1_700_000_100
    commit.author_timezone = commit.commit_timezone = 0
    commit.message = b"Update README"
    source.object_store.add_objects([(blob, None), (tree, None), (commit, None)])
    reference = Ref(f"refs/heads/{BRANCH}".encode())
    source.refs[reference] = commit.id
    buffer = io.BytesIO()
    write_bundle(buffer, create_bundle_from_repo(source, refs=[reference], prerequisites=[base.encode()]))
    return Publication(git=git, owner=owner, base=base, head=commit.id.decode(), contents=buffer.getvalue())


async def test_publication_imports_objects_once_and_preserves_main(
    publication: Publication, fake_stores: FakeStores
) -> None:
    data = publication
    assert await data.git.publish_agent_bundle(data.owner, "repo", BRANCH, "main", data.contents, None) == data.head
    objects = dict(fake_stores.blob.objects)
    assert await data.git.publish_agent_bundle(data.owner, "repo", BRANCH, "main", data.contents, None) == data.head
    assert fake_stores.blob.objects == objects
    assert await data.git.git_refs.branch_heads(data.owner, "repo", "main", BRANCH) == (data.base, data.head)
    loaded = await data.git.load_repository(data.owner, "repo")
    commit = loaded.object_store[ObjectID(data.head.encode())]
    assert isinstance(commit, Commit)
    assert commit.parents == [ObjectID(data.base.encode())]
    tree = loaded.object_store[commit.tree]
    assert isinstance(tree, Tree)
    _, blob_id = tree[b"README.md"]
    assert loaded.object_store[blob_id].as_raw_string() == b"Agent changed this README.\n"


async def test_publication_rejects_a_branch_changed_outside_the_workspace(
    publication: Publication, fake_stores: FakeStores
) -> None:
    data = publication
    key = f"{data.owner}/repo.git/refs/refs/heads/{BRANCH}"
    await fake_stores.redis.set(key, data.base)
    with pytest.raises(ConflictError, match="changed outside"):
        await data.git.publish_agent_bundle(data.owner, "repo", BRANCH, "main", data.contents, None)
    assert await data.git.git_refs.branch_heads(data.owner, "repo", "main", BRANCH) == (data.base, data.base)


async def test_publication_never_rewinds_existing_commits(publication: Publication) -> None:
    data = publication
    await data.git.publish_agent_bundle(data.owner, "repo", BRANCH, "main", data.contents, None)
    source = await data.git.load_repository(data.owner, "repo")
    previous = source.object_store[ObjectID(data.head.encode())]
    assert isinstance(previous, Commit)
    advanced = Commit.from_raw_string(Commit.type_num, previous.as_raw_string())
    assert isinstance(advanced, Commit)
    advanced.parents = [previous.id]
    advanced.message = b"Another actual commit"
    source.object_store.add_objects([(advanced, None)])
    source.refs[Ref(f"refs/heads/{BRANCH}".encode())] = advanced.id
    await data.git.save_changes(data.owner, "repo")
    with pytest.raises(ConflictError, match="fast-forward"):
        await data.git.publish_agent_bundle(data.owner, "repo", BRANCH, "main", data.contents, advanced.id.decode())
    assert await data.git.git_refs.branch_heads(data.owner, "repo", "main", BRANCH) == (data.base, advanced.id.decode())


async def test_main_advancing_during_publication_prevents_the_branch_cas(
    publication: Publication, fake_stores: FakeStores, mocker: MockerFixture
) -> None:
    data = publication
    publish = data.git.git_refs.publish_branch
    advanced = "a" * 40

    async def race(
        owner: str, name: str, branch: str, commit: str, expected: str | None, base: str, base_commit: str
    ) -> bool:
        await fake_stores.redis.set(f"{owner}/{name}.git/refs/refs/heads/{base}", advanced)
        return await publish(owner, name, branch, commit, expected, base, base_commit)

    mocker.patch.object(data.git.git_refs, "publish_branch", side_effect=race)
    with pytest.raises(ConflictError, match="changed during publication"):
        await data.git.publish_agent_bundle(data.owner, "repo", BRANCH, "main", data.contents, None)
    assert await data.git.git_refs.branch_heads(data.owner, "repo", "main", BRANCH) == (advanced, None)


async def test_missing_base_ref_prevents_publication(publication: Publication, fake_stores: FakeStores) -> None:
    data = publication
    await fake_stores.redis.delete(f"{data.owner}/repo.git/refs/refs/heads/main")
    with pytest.raises(ConflictError, match="base branch does not exist"):
        await data.git.publish_agent_bundle(data.owner, "repo", BRANCH, "main", data.contents, None)
    assert await data.git.git_refs.branch_heads(data.owner, "repo", "main", BRANCH) == (None, None)


async def test_bundle_cannot_publish_extra_refs(publication: Publication) -> None:
    data = publication
    with read_bundle(io.BytesIO(data.contents)) as bundle:
        bundle.references[Ref(b"refs/heads/main")] = ObjectID(data.head.encode())
        buffer = io.BytesIO()
        write_bundle(buffer, bundle)
    with pytest.raises(InvalidInputError, match="exactly the publication branch"):
        await data.git.publish_agent_bundle(data.owner, "repo", BRANCH, "main", buffer.getvalue(), None)
    assert await data.git.git_refs.branch_heads(data.owner, "repo", "main", BRANCH) == (data.base, None)


@pytest.mark.parametrize("branch", ["", "agents/../main", "invalid branch"])
async def test_publication_requires_a_valid_git_branch(publication: Publication, branch: str) -> None:
    data = publication
    with pytest.raises(InvalidInputError, match="Invalid publication branch"):
        await data.git.publish_agent_bundle(data.owner, "repo", branch, "main", data.contents, None)


async def test_publication_cannot_replace_its_base(publication: Publication) -> None:
    data = publication
    with pytest.raises(InvalidInputError, match="must not replace the base"):
        await data.git.publish_agent_bundle(data.owner, "repo", "main", "main", data.contents, None)
