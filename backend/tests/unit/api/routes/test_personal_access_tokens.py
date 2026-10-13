from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import pytest
from fastapi import HTTPException

from app.clients.personal_access_tokens import AUTHENTICATION_LIMIT
from app.config import settings
from app.schemas.personal_access_tokens import GitScope, PersonalAccessTokenCreate
from app.services.personal_access_tokens import ISSUANCE_ATTEMPTS, PAT_FORMAT_PREFIX, PersonalAccessTokenService
from tests.unit.api.routes.test_authorization import add_repository, add_user, headers

if TYPE_CHECKING:
    from fastapi.testclient import TestClient
    from pytest import LogCaptureFixture
    from pytest_mock import MockerFixture

    from tests.unit.utils.fakes import FakeStores

TOKENS_URL = f"{settings.API_V1_STR}/users/me/personal-access-tokens/"


def create_token(
    client: TestClient, user_headers: dict[str, str], *, scopes: list[str] | None = None
) -> dict[str, object]:
    response = client.post(
        TOKENS_URL,
        headers=user_headers,
        json={
            "name": "Laptop",
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
    body = {"name": "Replacement", "scopes": ["git:read"]}
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
    with pytest.raises(HTTPException) as caught:
        await PersonalAccessTokenService(store, fake_stores.users).authenticate(credential, GitScope.READ)
    assert caught.value.status_code == 401
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
    body = PersonalAccessTokenCreate(name="Key", scopes=[GitScope.READ])
    old = await service.issue(body, owner)
    row = await service.owned_token(old.id, owner)
    issue = mocker.patch.object(fake_stores.personal_access_tokens, "issue", return_value=False)
    with pytest.raises(HTTPException) as caught:
        await service.rotate(old.id, body, owner)
    assert caught.value.status_code == 503
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
