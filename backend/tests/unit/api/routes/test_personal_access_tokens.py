from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import pytest

from app.clients.personal_access_tokens import AUTHENTICATION_LIMIT
from app.config import settings
from app.entities.authorization import RepositoryCollaborator
from app.exceptions import InvalidPersonalAccessTokenError, TokenIssuanceError
from app.schemas.personal_access_tokens import PersonalAccessTokenCreate, TokenScope
from app.services.personal_access_tokens import ISSUANCE_ATTEMPTS, PAT_FORMAT_PREFIX, PersonalAccessTokenService
from tests.unit.api.routes.test_authorization import add_repository, add_user, headers
from tests.unit.utils.git import seed_merge_repository

if TYPE_CHECKING:
    from fastapi.testclient import TestClient
    from pytest import LogCaptureFixture
    from pytest_mock import MockerFixture

    from tests.unit.utils.fakes import FakeStores

TOKENS_URL = f"{settings.API_V1_STR}/users/me/personal-access-tokens/"


def create_token(
    client: TestClient,
    user_headers: dict[str, str],
    *,
    scopes: list[str] | None = None,
    repository_ids: list[str] | None = None,
) -> dict[str, object]:
    options = client.get(f"{TOKENS_URL}repositories", headers=user_headers).json()
    if not options:
        client.post(
            f"{settings.API_V1_STR}/repositories/",
            headers=user_headers,
            json={
                "owner": client.get(f"{settings.API_V1_STR}/users/me", headers=user_headers).json()["name"],
                "name": "selected",
            },
        )
        options = client.get(f"{TOKENS_URL}repositories", headers=user_headers).json()
    response = client.post(
        TOKENS_URL,
        headers=user_headers,
        json={
            "name": "Laptop",
            "repository_ids": repository_ids if repository_ids is not None else [option["id"] for option in options],
            "scopes": scopes or ["git:read"],
            "expires_at": (datetime.now(UTC) + timedelta(days=30)).isoformat(),
        },
    )
    assert response.status_code == 201
    assert response.headers["cache-control"] == "private, no-store"
    return response.json()


def test_issue_stores_only_argon2id_hash_and_safe_metadata(
    client: TestClient, fake_stores: FakeStores, caplog: LogCaptureFixture
) -> None:
    owner = add_user(fake_stores, "owner")
    caplog.set_level("INFO")
    issued = create_token(client, headers(owner))
    token = str(issued["token"])
    row = next(iter(fake_stores.personal_access_tokens.items.values()))
    assert token.startswith(PAT_FORMAT_PREFIX)
    assert row.secret_hash.startswith("$argon2id$v=19$m=19456,t=2,p=1$")
    secret = token.split(".")[1]
    assert row.secret_last4 == secret[-4:]
    assert token not in caplog.text
    assert secret not in caplog.text
    assert "PAT issued" in caplog.text
    listed = client.get(TOKENS_URL, headers=headers(owner))
    assert listed.status_code == 200
    assert listed.headers["cache-control"] == "private, no-store"
    assert "token" not in listed.json()[0]
    assert "secret_hash" not in listed.json()[0]
    assert token not in listed.text
    assert secret not in listed.text
    assert not row.last_used_at


@pytest.mark.parametrize("transport", ["basic", "bearer", "header"])
def test_pat_authenticates_git_and_updates_last_use(
    client: TestClient, fake_stores: FakeStores, transport: str
) -> None:
    owner = add_user(fake_stores, "owner")
    add_repository(fake_stores, owner)
    token = str(create_token(client, headers(owner))["token"])
    url = f"{settings.API_V1_STR}/owner/repo.git/info/refs?service=git-upload-pack"
    if transport == "basic":
        response = client.get(url, auth=(owner.name, token))
    else:
        credential_headers = {"Authorization": f"Bearer {token}"} if transport == "bearer" else {"X-API-Key": token}
        response = client.get(url, headers=credential_headers)
    assert response.status_code == 200
    assert next(iter(fake_stores.personal_access_tokens.items.values())).last_used_at is not None
    assert client.get(TOKENS_URL, headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_pat_scopes_cannot_bypass_repository_roles(client: TestClient, fake_stores: FakeStores) -> None:
    owner = add_user(fake_stores, "owner")
    outsider = add_user(fake_stores, "outsider")
    add_repository(fake_stores, owner)
    read = str(create_token(client, headers(owner))["token"])
    outsider_write = str(create_token(client, headers(outsider), scopes=["git:write"])["token"])
    base = f"{settings.API_V1_STR}/owner/repo.git"
    discovery = f"{base}/info/refs?service=git-receive-pack"
    assert client.get(discovery, auth=(owner.name, read)).status_code == 403
    assert client.post(f"{base}/git-receive-pack", auth=(owner.name, read)).status_code == 403
    assert client.get(discovery, auth=(outsider.name, outsider_write)).status_code == 403
    assert (
        client.get(f"{base}/info/refs?service=git-upload-pack", auth=(outsider.name, outsider_write)).status_code == 403
    )
    write = str(create_token(client, headers(owner), scopes=["git:write"])["token"])
    assert client.get(discovery, auth=(owner.name, write)).status_code == 200
    assert client.get(f"{base}/info/refs?service=git-upload-pack", auth=(owner.name, write)).status_code == 200
    assert client.get(discovery, auth=(outsider.name, write)).status_code == 401


@pytest.mark.parametrize("state", ["expired", "revoked", "inactive", "bad_secret", "bad_hash"])
def test_invalid_pat_never_falls_back_to_public_read(client: TestClient, fake_stores: FakeStores, state: str) -> None:
    owner = add_user(fake_stores, "owner")
    add_repository(fake_stores, owner, private=False)
    issued = create_token(client, headers(owner))
    token = str(issued["token"])
    row = next(iter(fake_stores.personal_access_tokens.items.values()))
    if state == "expired":
        row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    elif state == "revoked":
        row.revoked_at = datetime.now(UTC)
    elif state == "inactive":
        owner.is_active = False
    elif state == "bad_hash":
        row.secret_hash = "invalid"
    else:
        token = token[:-1] + ("a" if token[-1] != "a" else "b")
    url = f"{settings.API_V1_STR}/owner/repo.git/info/refs?service=git-upload-pack"
    assert client.get(url, headers={"X-API-Key": token}).status_code == 401
    assert client.get(url).status_code == 200


def test_revoke_rotate_and_account_isolation(client: TestClient, fake_stores: FakeStores) -> None:
    owner = add_user(fake_stores, "owner")
    outsider = add_user(fake_stores, "outsider")
    add_repository(fake_stores, owner)
    issued = create_token(client, headers(owner))
    token_id = str(issued["id"])
    rotate_url = f"{TOKENS_URL}{token_id}/rotate"
    body = {"name": "Replacement", "scopes": ["git:read"], "repository_ids": issued["repository_ids"]}
    assert client.get(TOKENS_URL, headers=headers(outsider)).json() == []
    assert client.post(rotate_url, headers=headers(outsider), json=body).status_code == 404
    assert client.post(f"{TOKENS_URL}{token_id}/revoke", headers=headers(outsider), json={}).status_code == 404
    replacement = client.post(rotate_url, headers=headers(owner), json=body)
    assert replacement.status_code == 201
    new_token = replacement.json()["token"]
    git_url = f"{settings.API_V1_STR}/owner/repo.git/info/refs?service=git-upload-pack"
    assert client.get(git_url, auth=(owner.name, str(issued["token"]))).status_code == 401
    assert client.get(git_url, auth=(owner.name, new_token)).status_code == 200
    assert (
        client.post(
            f"{TOKENS_URL}{replacement.json()['id']}/revoke", headers=headers(owner), json={"reason": "Retired device"}
        ).status_code
        == 204
    )
    assert client.get(git_url, auth=(owner.name, new_token)).status_code == 401
    assert (
        client.post(f"{TOKENS_URL}{replacement.json()['id']}/revoke", headers=headers(owner), json={}).status_code
        == 204
    )
    listed = client.get(TOKENS_URL, headers=headers(owner)).json()
    assert {item["revoked_reason"] for item in listed} == {"Rotated", "Retired device"}
    assert client.post(rotate_url, headers=headers(owner), json=body).status_code == 409


@pytest.mark.parametrize(
    "credential",
    [
        "unknown_v1_x.y",
        "gitedge_pat_live_v2_a.b",
        "gitedge_pat_live_v1_bad",
        "gitedge_pat_live_v1_" + "a" * 24 + ".short",
    ],
)
async def test_format_rejected_before_database_lookup(
    fake_stores: FakeStores, mocker: MockerFixture, credential: str
) -> None:
    store = fake_stores.personal_access_tokens
    lookup = mocker.spy(store, "find_by_key_id")
    with pytest.raises(InvalidPersonalAccessTokenError):
        await PersonalAccessTokenService(store, fake_stores.users).authenticate(credential, TokenScope.READ)
    lookup.assert_not_called()


def test_authentication_rate_limit_and_recovery(client: TestClient, fake_stores: FakeStores) -> None:
    owner = add_user(fake_stores, "owner")
    add_repository(fake_stores, owner)
    token = str(create_token(client, headers(owner))["token"])
    row = next(iter(fake_stores.personal_access_tokens.items.values()))
    row.authentication_window_start = datetime.now(UTC)
    row.authentication_attempts = AUTHENTICATION_LIMIT
    url = f"{settings.API_V1_STR}/owner/repo.git/info/refs?service=git-upload-pack"
    response = client.get(url, auth=(owner.name, token))
    assert response.status_code == 429
    assert response.headers["retry-after"] == "60"
    row.authentication_window_start = datetime.now(UTC) - timedelta(minutes=2)
    assert client.get(url, auth=(owner.name, token)).status_code == 200
    assert row.authentication_attempts == 1


async def test_collision_retries_are_bounded_and_do_not_revoke_old_token(
    fake_stores: FakeStores, mocker: MockerFixture
) -> None:
    owner = add_user(fake_stores, "owner")
    service = PersonalAccessTokenService(fake_stores.personal_access_tokens, fake_stores.users)
    body = PersonalAccessTokenCreate(name="Key", scopes=[TokenScope.READ], repository_ids=[uuid.uuid4()])
    old = await service.issue(body, owner)
    row = await service.owned_token(old.id, owner)
    issue = mocker.patch.object(fake_stores.personal_access_tokens, "issue", return_value=False)
    with pytest.raises(TokenIssuanceError):
        await service.rotate(old.id, body, owner)
    assert issue.call_count == ISSUANCE_ATTEMPTS
    assert row.revoked_at is None


@pytest.mark.parametrize(
    "body",
    [
        {"name": "", "scopes": ["git:read"]},
        {"name": "key", "scopes": []},
        {"name": "key", "scopes": ["admin"]},
        {"name": "key", "scopes": ["git:read"], "expires_at": "2020-01-01T00:00:00Z"},
    ],
)
def test_input_validation(client: TestClient, fake_stores: FakeStores, body: dict[str, object]) -> None:
    owner = add_user(fake_stores, "owner")
    assert client.post(TOKENS_URL, headers=headers(owner), json=body).status_code == 422
    assert not fake_stores.personal_access_tokens.items


@pytest.mark.parametrize("transport", ["basic", "bearer", "header"])
def test_git_token_is_limited_to_selected_repository(
    client: TestClient, fake_stores: FakeStores, transport: str
) -> None:
    owner = add_user(fake_stores, "owner")
    selected = add_repository(fake_stores, owner, "selected")
    add_repository(fake_stores, owner, "other", private=False)
    token = str(create_token(client, headers(owner), scopes=["git:write"], repository_ids=[str(selected.id)])["token"])
    auth = (owner.name, token) if transport == "basic" else None
    credential_headers = (
        {"Authorization": f"Bearer {token}"}
        if transport == "bearer"
        else {"X-API-Key": token}
        if transport == "header"
        else {}
    )
    for service in ("git-upload-pack", "git-receive-pack"):
        assert (
            client.get(
                f"{settings.API_V1_STR}/owner/selected.git/info/refs?service={service}",
                headers=credential_headers,
                auth=auth,
            ).status_code
            == 200
        )
        assert (
            client.get(
                f"{settings.API_V1_STR}/owner/other.git/info/refs?service={service}",
                headers=credential_headers,
                auth=auth,
            ).status_code
            == 403
        )


@pytest.mark.parametrize(
    "scope", ["repository:read", "git:write", "issues:write", "pull_requests:write", "repository:write"]
)
def test_token_operations_are_independent(client: TestClient, fake_stores: FakeStores, scope: str) -> None:
    owner = add_user(fake_stores, "owner")
    repo = add_repository(fake_stores, owner)
    seed_merge_repository(fake_stores, "owner", "repo")
    token = str(create_token(client, headers(owner), scopes=[scope], repository_ids=[str(repo.id)])["token"])
    auth = {"Authorization": f"Bearer {token}"}
    base = f"{settings.API_V1_STR}/repositories/owner/repo"
    assert client.get(base, headers=auth).status_code == (200 if scope == "repository:read" else 403)
    assert client.post(f"{base}/issues", headers=auth, json={"title": "Automated issue"}).status_code == (
        201 if scope == "issues:write" else 403
    )
    assert client.post(
        f"{base}/pulls", headers=auth, json={"title": "Automated PR", "head_branch": "feature"}
    ).status_code == (201 if scope == "pull_requests:write" else 403)
    assert client.patch(base, headers=auth, json={"name": "renamed"}).status_code == (
        200 if scope == "repository:write" else 403
    )
    name = "renamed" if scope == "repository:write" else "repo"
    assert client.get(
        f"{settings.API_V1_STR}/owner/{name}.git/info/refs?service=git-receive-pack", headers=auth
    ).status_code == (200 if scope == "git:write" else 403)
    assert client.get(f"{settings.API_V1_STR}/users/me", headers=auth).status_code == 401
    assert client.get(TOKENS_URL, headers=auth).status_code == 401


def test_api_repository_selection_survives_rename_and_does_not_expand(
    client: TestClient, fake_stores: FakeStores
) -> None:
    owner = add_user(fake_stores, "owner")
    selected = add_repository(fake_stores, owner, "selected")
    add_repository(fake_stores, owner, "other")
    token = str(
        create_token(
            client,
            headers(owner),
            scopes=["repository:read", "repository:write", "issues:write"],
            repository_ids=[str(selected.id)],
        )["token"]
    )
    auth = {"X-API-Key": token}
    base = f"{settings.API_V1_STR}/repositories/owner"
    assert client.patch(f"{base}/selected", headers=auth, json={"name": "renamed"}).status_code == 200
    assert client.get(f"{base}/renamed", headers=auth).status_code == 200
    assert client.get(f"{base}/other", headers=auth).status_code == 403
    assert client.post(f"{base}/other/issues", headers=auth, json={"title": "Not allowed"}).status_code == 403
    assert client.patch(f"{base}/other", headers=auth, json={"name": "forbidden"}).status_code == 403


def test_pr_write_token_cannot_merge_through_either_endpoint(client: TestClient, fake_stores: FakeStores) -> None:
    owner = add_user(fake_stores, "owner")
    repo = add_repository(fake_stores, owner)
    seed_merge_repository(fake_stores, "owner", "repo")
    token = str(
        create_token(client, headers(owner), scopes=["pull_requests:write"], repository_ids=[str(repo.id)])["token"]
    )
    auth = {"Authorization": f"Bearer {token}"}
    base = f"{settings.API_V1_STR}/repositories/owner/repo/pulls"
    pull = client.post(base, headers=auth, json={"title": "PR", "head_branch": "feature"}).json()
    url = f"{base}/{pull['number']}"
    assert client.patch(url, headers=auth, json={"state": "merged"}).status_code == 403
    assert client.post(f"{url}/merge", headers=auth, json={}).status_code == 403
    merge = str(
        create_token(client, headers(owner), scopes=["pull_requests:merge"], repository_ids=[str(repo.id)])["token"]
    )
    assert client.post(f"{url}/merge", headers={"Authorization": f"Bearer {merge}"}, json={}).status_code == 200


def test_comment_id_routes_cannot_escape_token_repository_selection(
    client: TestClient, fake_stores: FakeStores
) -> None:
    owner = add_user(fake_stores, "owner")
    selected = add_repository(fake_stores, owner, "selected")
    add_repository(fake_stores, owner, "other")
    token = str(
        create_token(client, headers(owner), scopes=["comments:write"], repository_ids=[str(selected.id)])["token"]
    )
    auth = {"Authorization": f"Bearer {token}"}
    for name in ("selected", "other"):
        base = f"{settings.API_V1_STR}/repositories/owner/{name}"
        issue = client.post(f"{base}/issues", headers=headers(owner), json={"title": "Issue"}).json()
        comment = client.post(
            f"{base}/issues/{issue['number']}/comments", headers=headers(owner), json={"body": "Comment"}
        ).json()
        url = f"{settings.API_V1_STR}/comments/{comment['id']}"
        assert client.patch(url, headers=auth, json={"body": "Updated"}).status_code == (
            200 if name == "selected" else 403
        )
        assert client.delete(url, headers=auth).status_code == (204 if name == "selected" else 403)


async def test_token_cannot_outlive_repository_role_revocation(client: TestClient, fake_stores: FakeStores) -> None:
    owner = add_user(fake_stores, "owner")
    writer = add_user(fake_stores, "writer")
    repo = add_repository(fake_stores, owner)
    grant = RepositoryCollaborator(repository_id=repo.id, user_id=writer.id, role="admin")
    await fake_stores.authorization.save(grant)
    token = str(
        create_token(client, headers(writer), scopes=["repository:write"], repository_ids=[str(repo.id)])["token"]
    )
    url = f"{settings.API_V1_STR}/repositories/owner/repo"
    auth = {"Authorization": f"Bearer {token}"}
    assert client.patch(url, headers=auth, json={"description": "Allowed"}).status_code == 200
    await fake_stores.authorization.remove(grant)
    assert client.patch(url, headers=auth, json={"description": "Denied"}).status_code == 403


def test_rotation_changes_allowlist_and_permissions_atomically(client: TestClient, fake_stores: FakeStores) -> None:
    owner = add_user(fake_stores, "owner")
    first = add_repository(fake_stores, owner, "first")
    second = add_repository(fake_stores, owner, "second")
    issued = create_token(client, headers(owner), scopes=["issues:write"], repository_ids=[str(first.id)])
    response = client.post(
        f"{TOKENS_URL}{issued['id']}/rotate",
        headers=headers(owner),
        json={"name": "Replacement", "scopes": ["repository:read"], "repository_ids": [str(second.id)]},
    )
    assert response.status_code == 201
    base = f"{settings.API_V1_STR}/repositories/owner"
    assert client.get(f"{base}/first", headers={"Authorization": f"Bearer {issued['token']}"}).status_code == 401
    auth = {"Authorization": f"Bearer {response.json()['token']}"}
    assert client.get(f"{base}/first", headers=auth).status_code == 403
    assert client.get(f"{base}/second", headers=auth).status_code == 200
    assert client.post(f"{base}/second/issues", headers=auth, json={"title": "Denied"}).status_code == 403


@pytest.mark.parametrize("selection", [None, [], [str(uuid.uuid4())]])
def test_token_requires_explicit_accessible_repository_selection(
    client: TestClient, fake_stores: FakeStores, selection: list[str] | None
) -> None:
    owner = add_user(fake_stores, "owner")
    body = {"name": "Invalid selection", "scopes": ["git:read"]}
    if selection is not None:
        body["repository_ids"] = selection
    assert client.post(TOKENS_URL, headers=headers(owner), json=body).status_code == (400 if selection else 422)
    assert not fake_stores.personal_access_tokens.items


def test_legacy_empty_selection_denies_access_until_rotation(client: TestClient, fake_stores: FakeStores) -> None:
    owner = add_user(fake_stores, "owner")
    repo = add_repository(fake_stores, owner)
    issued = create_token(client, headers(owner), repository_ids=[str(repo.id)])
    row = next(iter(fake_stores.personal_access_tokens.items.values()))
    row.repository_ids = []
    url = f"{settings.API_V1_STR}/owner/repo.git/info/refs?service=git-upload-pack"
    assert client.get(url, headers={"Authorization": f"Bearer {issued['token']}"}).status_code == 403
    replacement = client.post(
        f"{TOKENS_URL}{issued['id']}/rotate",
        headers=headers(owner),
        json={"name": "Selected", "scopes": ["git:read"], "repository_ids": [str(repo.id)]},
    )
    assert replacement.status_code == 201
    assert client.get(url, headers={"Authorization": f"Bearer {replacement.json()['token']}"}).status_code == 200
