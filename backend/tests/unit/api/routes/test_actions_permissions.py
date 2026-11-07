from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import jwt
import pytest

from app.config import settings
from app.exceptions import WorkflowError
from app.schemas.authorization import RepositoryCollaborator
from app.services.actions.service import ActionsService
from tests.unit.api.routes.test_authorization import add_repository, add_user, headers
from tests.unit.api.routes.test_personal_access_tokens import create_token

if TYPE_CHECKING:
    from fastapi.testclient import TestClient
    from pytest_mock import MockerFixture

    from tests.unit.utils.fakes import FakeStores

API = settings.API_V1_STR


@pytest.mark.parametrize(("role", "write_status"), [("read", 403), ("write", 422), ("admin", 422)])
async def test_actions_honor_repository_grants_and_revocation(
    client: TestClient, fake_stores: FakeStores, mocker: MockerFixture, role: str, write_status: int
) -> None:
    owner, collaborator = add_user(fake_stores, "owner"), add_user(fake_stores, "collaborator")
    repository = add_repository(fake_stores, owner)
    grant = RepositoryCollaborator(repository_id=repository.id, user_id=collaborator.id, role=role)
    await fake_stores.authorization.save(grant)
    path = f"{API}/repositories/owner/repo/actions"
    credential = headers(collaborator)
    assert client.get(f"{path}/runs", headers=credential).status_code == 200
    dispatch = mocker.patch.object(ActionsService, "dispatch", side_effect=WorkflowError("No workflows"))
    assert (
        client.post(f"{path}/dispatch", headers=credential, json={"workflow": ".gitedge/workflow/ci.yaml"}).status_code
        == write_status
    )
    assert dispatch.call_count == (role != "read")
    await fake_stores.authorization.remove(grant)
    assert client.get(f"{path}/runs", headers=credential).status_code == 403


@pytest.mark.parametrize(
    ("scope", "read_status", "write_status"),
    [("git:write", 403, 403), ("actions:read", 200, 403), ("actions:write", 200, 422)],
)
def test_actions_pat_intersects_scopes_and_repository_selection(
    client: TestClient, fake_stores: FakeStores, mocker: MockerFixture, scope: str, read_status: int, write_status: int
) -> None:
    owner = add_user(fake_stores, "owner")
    selected = add_repository(fake_stores, owner)
    add_repository(fake_stores, owner, "other")
    token = create_token(client, headers(owner), scopes=[scope], repository_ids=[str(selected.id)])
    credential = {"X-API-Key": str(token["token"])}
    path = f"{API}/repositories/owner/repo/actions"
    assert client.get(f"{path}/runs", headers=credential).status_code == read_status
    mocker.patch.object(ActionsService, "dispatch", side_effect=WorkflowError("No workflows"))
    assert (
        client.post(f"{path}/dispatch", headers=credential, json={"workflow": ".gitedge/workflow/ci.yaml"}).status_code
        == write_status
    )
    assert client.get(f"{API}/repositories/owner/other/actions/runs", headers=credential).status_code == 403


@pytest.mark.parametrize("git_suffix", [".git", ""])
@pytest.mark.parametrize(
    ("scope", "expired", "status"), [("git:read", False, 200), ("git:write", False, 401), ("git:read", True, 401)]
)
def test_checkout_token_is_repository_scoped_and_read_only(
    client: TestClient, fake_stores: FakeStores, scope: str, git_suffix: str, *, expired: bool, status: int
) -> None:
    owner = add_user(fake_stores, "owner")
    repository = add_repository(fake_stores, owner)
    add_repository(fake_stores, owner, "other")
    token = jwt.encode(
        {
            "sub": "actions",
            "repo": str(repository.id),
            "run": str(uuid.uuid4()),
            "scope": scope,
            "exp": datetime.now(UTC) + timedelta(seconds=-1 if expired else 60),
        },
        settings.SECRET_KEY,
        algorithm="HS256",
    )
    credential = ("x-access-token", token)
    path = f"{API}/owner/repo{git_suffix}"
    assert client.get(f"{path}/info/refs?service=git-upload-pack", auth=credential).status_code == status
    assert client.post(f"{path}/git-receive-pack", auth=credential).status_code == (403 if status == 200 else 401)
    assert client.get(
        f"{API}/owner/other{git_suffix}/info/refs?service=git-upload-pack", auth=credential
    ).status_code == (403 if status == 200 else 401)
