"""Real merge graphs through HTTP using in-memory stores."""

import uuid
from typing import TYPE_CHECKING

import pytest
from dulwich.objects import Blob, Commit, ObjectID, Tree
from fastapi.concurrency import run_in_threadpool

from app.clients.git import GitStore
from app.config import settings
from app.schemas.repositories import MergeMessage, MergeMethod
from app.services.git.merges import GitMergeService, calculate_merge
from app.services.git.repositories import GitService
from app.services.git.repository import BlobRepository
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
    packs, refs = await GitStore(fake_stores.blob, fake_stores.redis).load(f"{OWNER}/repo.git")
    assert "refs/heads/feature" not in refs
    repo = BlobRepository(fake_stores.blob, f"{OWNER}/repo.git" + "/packs/", packs)
    repo.load_from_storage(refs)
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
    response = client.post(f"{pull}/merge", headers=superuser_token_headers, json={"method": method})
    assert response.status_code == 409
    assert "code.txt" in response.json()["detail"]
    assert "Resolve them on the PR branch" in response.json()["detail"]
    assert fake_stores.redis.values[f"{OWNER}/repo.git/refs/refs/heads/main"] == base.encode()
    assert fake_stores.redis.values[f"{OWNER}/repo.git/refs/refs/heads/feature"] == head.encode()
    assert client.get(pull).json()["state"] == "open"
    assert client.get(f"{pull}/events").json() == []


@pytest.mark.parametrize("method", ["merge", "squash", "rebase"])
@pytest.mark.parametrize("conflict", [False, True])
def test_mergeability_is_read_only_cached_and_tracks_both_tips(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    fake_stores: FakeStores,
    mocker: MockerFixture,
    method: str,
    conflict: bool,
) -> None:
    base, first, head = seed_merge_repository(fake_stores, OWNER, "repo", conflict=conflict)
    pull = create(client, superuser_token_headers)
    blobs, refs = fake_stores.blob.objects.copy(), fake_stores.redis.values.copy()
    calculate = mocker.patch("app.services.git.merges.calculate_merge", wraps=calculate_merge)
    response = client.get(f"{pull}/mergeability", params={"method": method})
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["mergeable"] is not conflict
    assert data["base_commit"] == base
    assert data["head_commit"] == head
    assert data["conflicting_files"] == (["code.txt"] if conflict else [])
    assert fake_stores.blob.objects == blobs
    assert fake_stores.redis.values == refs
    assert client.get(pull).json()["state"] == "open"
    assert client.get(f"{pull}/events").json() == []
    assert client.get(f"{pull}/mergeability", params={"method": method}).json() == data
    assert calculate.call_count == 1
    assert calculate.call_args.kwargs["write_objects"] is False
    changed_base, _, changed_head = seed_merge_repository(fake_stores, OWNER, "repo", conflict=not conflict)
    updated = client.get(f"{pull}/mergeability", params={"method": method}).json()
    assert updated["mergeable"] is conflict
    assert updated["base_commit"] == changed_base
    assert updated["head_commit"] == changed_head
    assert calculate.call_count == 2
    fake_stores.redis.values[f"{OWNER}/repo.git/refs/refs/heads/feature"] = first.encode()
    updated_head = client.get(f"{pull}/mergeability", params={"method": method}).json()
    assert updated_head["base_commit"] == changed_base
    assert updated_head["head_commit"] == first
    assert calculate.call_count == 3
    other = "rebase" if method != "rebase" else "merge"
    assert client.get(f"{pull}/mergeability", params={"method": other}).status_code == 200
    assert calculate.call_count == 4


def test_mergeability_branch_and_policy_failures(
    client: TestClient, superuser_token_headers: dict[str, str], fake_stores: FakeStores
) -> None:
    base, _, head = seed_merge_repository(fake_stores, OWNER, "repo")
    pull = create(client, superuser_token_headers)
    assert client.get(f"{URL}/pulls/999/mergeability").status_code == 404
    assert client.get(f"{pull}/mergeability", params={"method": "unknown"}).status_code == 422
    client.patch(URL, headers=superuser_token_headers, json={"allow_merge_commit": False})
    assert "disabled" in client.get(f"{pull}/mergeability").json()["reason"]
    client.patch(URL, headers=superuser_token_headers, json={"allow_merge_commit": True})
    prefix = f"{OWNER}/repo.git/refs/refs/heads/"
    del fake_stores.redis.values[prefix + "feature"]
    assert "no longer exists" in client.get(f"{pull}/mergeability").json()["reason"]
    fake_stores.redis.values[prefix + "feature"] = base.encode()
    assert "no commits" in client.get(f"{pull}/mergeability").json()["reason"]
    fake_stores.redis.values[prefix + "feature"] = head.encode()
    assert (
        client.post(
            f"{pull}/merge", headers=superuser_token_headers, json={"head_commit": head, "base_commit": "f" * 40}
        ).status_code
        == 409
    )
    client.patch(pull, headers=superuser_token_headers, json={"state": "closed"})
    assert client.get(f"{pull}/mergeability").json()["mergeable"] is False


async def test_rebase_checks_each_commit_even_when_the_combined_diff_merges_cleanly(
    client: TestClient, superuser_token_headers: dict[str, str], fake_stores: FakeStores
) -> None:
    base, _, head = seed_merge_repository(fake_stores, OWNER, "repo", conflict=True, revert_first=True)
    pull = create(client, superuser_token_headers)
    assert client.get(f"{pull}/mergeability", params={"method": "merge"}).json()["mergeable"] is True
    assert client.get(f"{pull}/mergeability", params={"method": "squash"}).json()["mergeable"] is True
    result = client.get(f"{pull}/mergeability", params={"method": "rebase"}).json()
    assert result["mergeable"] is False
    assert result["conflicting_files"] == ["code.txt"]
    git = GitMergeService(
        GitService(GitStore(fake_stores.blob, fake_stores.redis), fake_stores.cache, fake_stores.repository)
    )
    repo = await git.git.load_repository(OWNER, "repo", fresh=True)
    before = repo.get_pending_changes()
    await run_in_threadpool(
        calculate_merge,
        repo,
        ObjectID(base.encode()),
        ObjectID(head.encode()),
        MergeMethod.MERGE,
        b"Read only\n",
        b"Owner <owner@example.com>",
        write_objects=False,
    )
    assert repo.get_pending_changes() == before
    repo.object_store.close()


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
        response = client.post(f"{pull}/merge", headers=superuser_token_headers, json={"method": method})
        assert response.status_code == 409
        assert "disabled" in response.json()["detail"]
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
    publish = fake_stores.redis.compare_and_set
    changed = "f" * 40

    async def advance_then_publish(expected: dict[str, str | None], updates: dict[str, str | None]) -> bool:
        fake_stores.redis.values[f"{OWNER}/repo.git/refs/refs/heads/{branch}"] = changed.encode()
        return await publish(expected, updates)

    mocker.patch.object(fake_stores.redis, "compare_and_set", side_effect=advance_then_publish)
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
    git = GitMergeService(
        GitService(GitStore(fake_stores.blob, fake_stores.redis), fake_stores.cache, fake_stores.repository)
    )
    repo = await git.git.load_repository(OWNER, "repo", fresh=True)
    result = await run_in_threadpool(
        calculate_merge,
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
