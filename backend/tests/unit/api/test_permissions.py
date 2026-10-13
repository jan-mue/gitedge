from typing import TYPE_CHECKING, Annotated

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.api.dependencies import (
    CurrentUser,
    OptionalUser,
    get_authorization_service,
    get_current_user,
    get_optional_user,
)
from app.api.permissions import require_permission
from app.entities.users import User
from app.services.authorization import new_enforcer
from tests.unit.api.routes.test_authorization import add_repository, add_user, service

if TYPE_CHECKING:
    from tests.unit.utils.fakes import FakeStores


@pytest.mark.parametrize("user_dep", [OptionalUser, get_optional_user])
def test_chained_authentication_returns_user_and_uses_dependency_cache(
    fake_stores: FakeStores, user_dep: object
) -> None:
    owner = add_user(fake_stores, "owner")
    add_repository(fake_stores, owner)
    app = FastAPI()
    authentication_calls = []
    handler_calls = []

    async def authenticate() -> User:
        authentication_calls.append(owner)
        return owner

    app.dependency_overrides[get_optional_user] = authenticate
    app.dependency_overrides[get_authorization_service] = lambda: service(fake_stores)
    permission = require_permission("repository:write", user_dep=user_dep)

    @app.get("/{owner}/{repo}")
    async def route(
        owner: str,
        repo: str,
        current_user: Annotated[User | None, Depends(permission)],
        authenticated_user: OptionalUser,
    ) -> dict[str, str]:
        assert isinstance(current_user, User)
        assert current_user is authenticated_user
        handler_calls.append((owner, repo))
        return {"user": current_user.name}

    with TestClient(app) as client:
        response = client.get("/owner/repo")
    assert response.status_code == 200
    assert response.json() == {"user": "owner"}
    assert response.headers["cache-control"] == "private, no-store"
    assert authentication_calls == [owner]
    assert handler_calls == [("owner", "repo")]
    parameters = app.openapi()["paths"]["/{owner}/{repo}"]["get"]["parameters"]
    assert [(param["name"], param["in"]) for param in parameters] == [("owner", "path"), ("repo", "path")]


def test_chained_permission_denies_before_handler(fake_stores: FakeStores) -> None:
    owner = add_user(fake_stores, "owner")
    outsider = add_user(fake_stores, "outsider")
    add_repository(fake_stores, owner)
    app = FastAPI()
    app.dependency_overrides[get_current_user] = lambda: outsider
    app.dependency_overrides[get_authorization_service] = lambda: service(fake_stores)
    handler_calls = []

    @app.get("/{owner}/{repo}", dependencies=[Depends(require_permission("repository:read", user_dep=CurrentUser))])
    async def route(owner: str, repo: str) -> dict[str, str]:
        handler_calls.append((owner, repo))
        return {"repo": repo}

    with TestClient(app) as client:
        assert client.get("/owner/repo").status_code == 403
    assert handler_calls == []


def test_optional_user_allows_anonymous_public_reads_but_not_private_reads(fake_stores: FakeStores) -> None:
    owner = add_user(fake_stores, "owner")
    add_repository(fake_stores, owner, "public", private=False)
    add_repository(fake_stores, owner, "private")
    app = FastAPI()
    app.dependency_overrides[get_optional_user] = lambda: None
    app.dependency_overrides[get_authorization_service] = lambda: service(fake_stores)

    @app.get("/{owner}/{repo}", dependencies=[Depends(require_permission("repository:read", user_dep=OptionalUser))])
    async def route(owner: str, repo: str) -> dict[str, str]:
        return {"owner": owner, "repo": repo}

    with TestClient(app) as client:
        public = client.get("/owner/public")
        assert public.status_code == 200
        assert "cache-control" not in public.headers
        private = client.get("/owner/private")
        assert private.status_code == 401
        assert private.headers["www-authenticate"] == "Bearer"


async def test_async_enforcers_load_policy_without_sharing_request_grants() -> None:
    first = await new_enforcer()
    second = await new_enforcer()
    await first.add_grouping_policy("alice", "owner", "repository:one")
    assert first.enforce("alice", "repository:one", "repository:read")
    assert first.enforce("alice", "repository:one", "repository:owner")
    assert not first.enforce("alice", "repository:two", "repository:read")
    assert not second.enforce("alice", "repository:one", "repository:read")


def test_rejects_invalid_authentication_dependency() -> None:
    with pytest.raises(TypeError, match="user_dep"):
        require_permission("repository:read", user_dep="current_user")
