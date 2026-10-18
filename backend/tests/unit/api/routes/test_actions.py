from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import jwt

from app.config import settings

if TYPE_CHECKING:
    from fastapi.testclient import TestClient

    from tests.unit.utils.fakes import FakeStores


OWNER = settings.FIRST_SUPERUSER.split("@")[0]
PATH = f"{settings.API_V1_STR}/repositories/{OWNER}/actions-repo"


def test_empty_repository_actions_and_dispatch_authorization(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    assert (
        client.post(f"{settings.API_V1_STR}/repositories/", json={"owner": OWNER, "name": "actions-repo"}).status_code
        == 201
    )
    assert client.get(f"{PATH}/actions/workflows").json() == []
    assert client.get(f"{PATH}/actions/runs").json() == []
    assert client.post(f"{PATH}/actions/dispatch", json={"workflow": ".gitedge/workflow/ci.yaml"}).status_code == 401
    assert client.post(f"{PATH}/actions/runs/{uuid.uuid4()}/cancel", headers=superuser_token_headers).status_code == 404


async def test_private_actions_history_requires_owner(
    client: TestClient,
    fake_stores: FakeStores,
    superuser_token_headers: dict[str, str],
    normal_user_token_headers: dict[str, str],
) -> None:
    client.post(f"{settings.API_V1_STR}/repositories/", json={"owner": OWNER, "name": "actions-repo"})
    repository = await fake_stores.repository.get_by_owner_and_name(OWNER, "actions-repo")
    repository.is_private = True
    assert client.get(f"{PATH}/pulls/1/checks").status_code == 404
    assert client.get(f"{PATH}/actions/runs").status_code == 404
    assert client.get(f"{PATH}/actions/runs", headers=normal_user_token_headers).status_code == 404
    assert client.get(f"{PATH}/actions/runs", headers=superuser_token_headers).status_code == 200
    assert (
        client.post(
            f"{PATH}/actions/dispatch",
            headers=normal_user_token_headers,
            json={"workflow": ".gitedge/workflow/ci.yaml"},
        ).status_code
        == 404
    )


def test_sandbox_endpoints_require_scoped_tokens(client: TestClient) -> None:
    assert client.get(f"{settings.API_V1_STR}/actions/state", params={"token": "invalid"}).status_code == 403
    assert client.post(f"{settings.API_V1_STR}/actions/complete", params={"token": "invalid"}).status_code == 403


def test_completion_rejects_read_only_state_tokens(client: TestClient) -> None:
    token = jwt.encode(
        {"repo": str(uuid.uuid4()), "run": str(uuid.uuid4()), "scope": "actions:state", "exp": 4102444800},
        settings.SECRET_KEY,
        algorithm="HS256",
    )
    assert client.post(f"{settings.API_V1_STR}/actions/complete", params={"token": token}).status_code == 403


def test_cache_capabilities_scope_upload_lookup_and_download_to_one_repository(client: TestClient) -> None:
    def capability(repo: uuid.UUID, scope: str = "actions:cache") -> str:
        return jwt.encode(
            {"repo": str(repo), "run": str(uuid.uuid4()), "scope": scope, "exp": 4102444800},
            settings.SECRET_KEY,
            algorithm="HS256",
        )

    repository = uuid.uuid4()
    token = capability(repository)
    path = f"{settings.API_V1_STR}/actions/cache"
    params = {"token": token, "key": "linux-bun", "version": "v1"}
    assert client.get(f"{path}/lookup", params=params).json() is None
    saved = client.post(path, params=params, content=b"portable cache")
    assert saved.status_code == 200
    entry = saved.json()
    assert client.get(f"{path}/lookup", params=params).json() == entry
    assert client.get(f"{path}/{entry['id']}", params={"token": token}).content == b"portable cache"
    other = capability(uuid.uuid4())
    assert client.get(f"{path}/lookup", params={**params, "token": other}).json() is None
    assert client.get(f"{path}/{entry['id']}", params={"token": other}).status_code == 404
    for wrong_scope in ["actions:state", "actions:complete"]:
        bad_params = {**params, "token": capability(repository, wrong_scope)}
        assert client.post(path, params=bad_params, content=b"invalid").status_code == 403
        assert client.get(f"{path}/lookup", params=bad_params).status_code == 403
    assert client.get(f"{path}/lookup", params={**params, "restore_keys": "x" * 513}).status_code == 422
