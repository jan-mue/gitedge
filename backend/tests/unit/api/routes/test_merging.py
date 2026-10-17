"""Real merge graphs through HTTP using in-memory stores."""

import uuid
from typing import TYPE_CHECKING

import pytest
from dulwich.objects import Blob, Commit, ObjectID, Tree

from app.clients.git_merges import GitMergeClient
from app.config import settings
from app.schemas.repositories import MergeMessage, MergeMethod
from app.services.blob_backend import BlobBackend, load_repository_from_storage
from app.services.blob_repository import BlobRepository
from app.services.merging import calculate_merge
from tests.unit.utils.git import seed_merge_repository

if TYPE_CHECKING:
    from fastapi.testclient import TestClient
    from pytest_mock import MockerFixture

    from tests.unit.utils.fakes import FakeStores

OWNER = settings.FIRST_SUPERUSER.split("@")[0]
URL = f"{settings.API_V1_STR}/repositories/{OWNER}/repo"


def create(client: TestClient, headers: dict[str, str]) -> str:
    response = client.post(
        f"{URL}/pulls", headers=headers, json={"title": "PR title", "body": "PR description", "head_branch": "feature"}
    )
    assert response.status_code == 201
    return f"{URL}/pulls/{response.json()['number']}"


@pytest.mark.parametrize("method", ["merge", "squash", "rebase"])
@pytest.mark.parametrize("template", list(MergeMessage))
async def test_merge_graph_messages_and_retained_views(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    fake_stores: FakeStores,
    method: str,
    template: MergeMessage,
) -> None:
    base, _, head = seed_merge_repository(fake_stores, OWNER, "repo")
    pull = create(client, superuser_token_headers)
    setting = {"merge": "merge_commit_message", "squash": "squash_commit_message", "rebase": "rebase_commit_message"}[
        method
    ]
    assert client.patch(URL, headers=superuser_token_headers, json={setting: template}).status_code == 200
    response = client.post(
        f"{pull}/merge", headers=superuser_token_headers, json={"method": method, "head_commit": head}
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["has_merged"]
    assert data["state"] == "merged"
    assert data["merged_commit_id"] != head
    packs, refs = await load_repository_from_storage(fake_stores.blob, fake_stores.redis, f"{OWNER}/repo.git")
    assert "refs/heads/feature" not in refs
    repo = BlobRepository()
    repo.load_from_storage(packs, refs)
    result = repo.object_store[ObjectID(refs["refs/heads/main"])]
    assert isinstance(result, Commit)
    assert result.id.decode() == data["merged_commit_id"]
    assert len(result.parents) == (2 if method == "merge" else 1)
    if method == "merge":
        assert result.parents == [base.encode(), head.encode()]
    elif method == "squash":
        assert result.parents == [base.encode()]
    else:
        parent = repo.object_store[result.parents[0]]
        assert isinstance(parent, Commit)
        assert parent.parents == [base.encode()]
        assert parent.message == b"Feature one\n\nFirst details"
        assert result.author == b"Original Author <original@example.com>"
    expected = {
        "default": "Merge feature into main",
        "title": "PR title",
        "title_description": "PR title\n\nPR description",
        "title_commits": "PR title\n\nFeature one\n\nFirst details\n\nFeature two",
    }[template]
    assert result.message.decode().strip() == expected
    tree = repo.object_store[result.tree]
    assert isinstance(tree, Tree)
    blob = repo.object_store[tree[b"code.txt"][1]]
    assert isinstance(blob, Blob)
    assert blob.data == b"feature\nsecond\nthird updated\n"
    marked = client.put(
        f"{pull}/reviewed-files",
        headers=superuser_token_headers,
        json={"base_commit": base, "head_commit": head, "path": "code.txt", "reviewed": True},
    )
    assert marked.status_code == 200, marked.text
    assert client.get(f"{pull}/review-workspace", headers=superuser_token_headers).json()["reviewed_paths"] == [
        "code.txt"
    ]
    assert client.get(f"{pull}/commits").json()["count"] == 2
    assert len(client.get(f"{pull}/files", params={"include_diff": False}).json()["files"]) == 2
    assert client.post(f"{pull}/merge", headers=superuser_token_headers, json={"method": method}).json() == data
    assert len(client.get(f"{pull}/events").json()) == 1
    assert client.patch(pull, headers=superuser_token_headers, json={"state": "open"}).status_code == 409
    repo.object_store.close()


@pytest.mark.parametrize("method", ["merge", "squash", "rebase"])
def test_conflicts_do_not_change_refs_or_state(
    client: TestClient, superuser_token_headers: dict[str, str], fake_stores: FakeStores, method: str
) -> None:
    base, _, head = seed_merge_repository(fake_stores, OWNER, "repo", conflict=True)
    pull = create(client, superuser_token_headers)
    assert client.post(f"{pull}/merge", headers=superuser_token_headers, json={"method": method}).status_code == 409
    assert fake_stores.redis.values[f"{OWNER}/repo.git/refs/refs/heads/main"] == base.encode()
    assert fake_stores.redis.values[f"{OWNER}/repo.git/refs/refs/heads/feature"] == head.encode()
    assert client.get(pull).json()["state"] == "open"
    assert client.get(f"{pull}/events").json() == []


def test_policies_permissions_stale_head_and_retention(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    normal_user_token_headers: dict[str, str],
    fake_stores: FakeStores,
) -> None:
    _, _, head = seed_merge_repository(fake_stores, OWNER, "repo")
    pull = create(client, superuser_token_headers)
    assert client.post(f"{pull}/merge", json={}).status_code == 401
    assert client.post(f"{pull}/merge", headers=normal_user_token_headers, json={}).status_code == 403
    assert (
        client.post(f"{pull}/merge", headers=superuser_token_headers, json={"head_commit": "f" * 40}).status_code == 409
    )
    assert (
        client.patch(
            URL,
            headers=superuser_token_headers,
            json={"allow_merge_commit": False, "allow_squash_merge": False, "allow_rebase_merge": False},
        ).status_code
        == 200
    )
    for method in ("merge", "squash", "rebase"):
        assert client.post(f"{pull}/merge", headers=superuser_token_headers, json={"method": method}).status_code == 409
    assert client.patch(pull, headers=superuser_token_headers, json={"state": "merged"}).status_code == 409
    client.patch(
        URL, headers=superuser_token_headers, json={"allow_merge_commit": True, "delete_branch_on_merge": False}
    )
    assert client.patch(pull, headers=superuser_token_headers, json={"state": "merged"}).status_code == 200
    assert fake_stores.redis.values[f"{OWNER}/repo.git/refs/refs/heads/feature"] == head.encode()


@pytest.mark.parametrize("branch", ["main", "feature"])
def test_concurrent_push_wins_over_merge(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    fake_stores: FakeStores,
    mocker: MockerFixture,
    branch: str,
) -> None:
    base, _, head = seed_merge_repository(fake_stores, OWNER, "repo")
    pull = create(client, superuser_token_headers)
    publish = fake_stores.redis.publish_merge
    changed = "f" * 40

    async def advance_then_publish(keys: list[str], base: str, head: str, commit: str, delete_branch: bool) -> bool:
        fake_stores.redis.values[f"{OWNER}/repo.git/refs/refs/heads/{branch}"] = changed.encode()
        return await publish(keys, base, head, commit, delete_branch)

    mocker.patch.object(fake_stores.redis, "publish_merge", side_effect=advance_then_publish)
    response = client.post(f"{pull}/merge", headers=superuser_token_headers, json={"method": "merge"})
    assert response.status_code == 409
    assert client.get(pull).json()["state"] == "open"
    assert fake_stores.redis.values[f"{OWNER}/repo.git/refs/refs/heads/{branch}"] == changed.encode()
    other = "feature" if branch == "main" else "main"
    assert (
        fake_stores.redis.values[f"{OWNER}/repo.git/refs/refs/heads/{other}"]
        == (head if other == "feature" else base).encode()
    )


async def test_retry_recovers_after_git_publication(
    client: TestClient, superuser_token_headers: dict[str, str], fake_stores: FakeStores
) -> None:
    base, _, head = seed_merge_repository(fake_stores, OWNER, "repo")
    pull = create(client, superuser_token_headers)
    git = GitMergeClient(fake_stores.blob, fake_stores.redis, fake_stores.cache, BlobBackend())
    repo = await git.load(OWNER, "repo")
    result = calculate_merge(
        repo,
        ObjectID(base.encode()),
        ObjectID(head.encode()),
        MergeMethod.MERGE,
        b"Recover merge\n",
        b"Owner <owner@example.com>",
    )
    assert await git.publish(
        OWNER, "repo", 1, repo, "main", "feature", result, True, pull_id=uuid.UUID(client.get(pull).json()["id"])
    )
    repo.object_store.close()
    # Git succeeded but the HTTP worker never saved the database state.
    assert client.get(pull).json()["state"] == "open"
    response = client.post(f"{pull}/merge", headers=superuser_token_headers, json={"method": "merge"})
    assert response.status_code == 200, response.text
    assert response.json()["merged_commit_id"] == result.commit
    assert len(client.get(f"{pull}/events").json()) == 1


def test_default_head_branch_is_kept(
    client: TestClient, superuser_token_headers: dict[str, str], fake_stores: FakeStores
) -> None:
    base, _, _ = seed_merge_repository(fake_stores, OWNER, "repo")
    response = client.post(
        f"{URL}/pulls",
        headers=superuser_token_headers,
        json={"title": "Backport default", "base_branch": "feature", "head_branch": "main"},
    )
    assert response.status_code == 201
    merged = client.post(f"{URL}/pulls/1/merge", headers=superuser_token_headers, json={"method": "merge"})
    assert merged.status_code == 200, merged.text
    assert fake_stores.redis.values[f"{OWNER}/repo.git/refs/refs/heads/main"] == base.encode()
