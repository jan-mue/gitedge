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
