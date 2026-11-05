from typing import TYPE_CHECKING, Annotated

import pytest
from fastapi import Depends, FastAPI, Request
from fastapi.testclient import TestClient

from app.api.dependencies import (
    CurrentUser,
    OptionalRepositoryUser,
    OptionalUser,
    get_authorization_service,
    get_current_user,
    get_optional_repository_user,
    get_optional_user,
)
from app.api.exception_handlers import application_exception_handler
from app.api.permissions import require_permission
from app.entities.authorization import RepositoryCollaborator
from app.entities.personal_access_tokens import PersonalAccessToken
from app.entities.users import User
from app.exceptions import ApplicationError
from app.services.authorization import policy_enforcer
from app.services.personal_access_tokens import AuthenticatedToken
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
    app.add_exception_handler(ApplicationError, application_exception_handler)
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
    app.add_exception_handler(ApplicationError, application_exception_handler)
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
    app.add_exception_handler(ApplicationError, application_exception_handler)
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


def test_static_policy_reuses_enforcer_without_retaining_request_roles() -> None:
    enforcer = policy_enforcer()
    assert enforcer is policy_enforcer()
    assert enforcer.enforce({"owner"}, "repository:read")
    assert enforcer.enforce({"owner"}, "repository:owner")
    assert not enforcer.enforce(set(), "repository:read")
    assert not enforcer.enforce({"org_admin"}, "repository:read")
    assert not enforcer.enforce({"owner"}, "organization:read")
    assert enforcer.enforce({"org_admin"}, "organization:read")


def test_rejects_invalid_authentication_dependency() -> None:
    with pytest.raises(TypeError, match="user_dep"):
        require_permission("repository:read", user_dep="current_user")


@pytest.mark.parametrize(
    ("operation", "scope", "role", "status"),
    [
        ("repository:read", "repository:read", "read", 200),
        ("repository:read", "git:read", "read", 403),
        ("git:read", "git:read", "read", 200),
        ("git:read", "repository:read", "read", 403),
        ("git:write", "git:write", "write", 200),
        ("git:write", "repository:write", "write", 403),
        ("repository:write", "repository:write", "admin", 200),
        ("repository:write", "repository:write", "write", 403),
        ("repository:delete", "repository:delete", "owner", 200),
        ("repository:delete", "repository:delete", "admin", 403),
        ("issues:write", "issues:write", "read", 200),
        ("issues:write", "repository:read", "owner", 403),
        ("pull_requests:write", "pull_requests:write", "read", 200),
        ("pull_requests:merge", "pull_requests:merge", "write", 200),
        ("pull_requests:merge", "pull_requests:write", "owner", 403),
        ("collaborators:write", "repository:write", "owner", 403),
        ("unknown:operation", "repository:read", "owner", 403),
    ],
)
async def test_operation_selects_both_account_permission_and_token_scope(
    fake_stores: FakeStores, operation: str, scope: str, role: str, status: int
) -> None:
    owner = add_user(fake_stores, "owner")
    actor = add_user(fake_stores, "actor")
    repository = add_repository(fake_stores, owner)
    await fake_stores.authorization.save(
        RepositoryCollaborator(repository_id=repository.id, user_id=actor.id, role=role)
    )
    token = PersonalAccessToken(owner_id=actor.id, repository_ids=[str(repository.id)], scopes=[scope])
    app = FastAPI()
    app.add_exception_handler(ApplicationError, application_exception_handler)
    app.dependency_overrides[get_authorization_service] = lambda: service(fake_stores)

    async def authenticate(request: Request) -> User:
        request.state.personal_access_token = AuthenticatedToken(actor, token)
        return actor

    app.dependency_overrides[get_optional_repository_user] = authenticate

    @app.get("/{owner}/{repo}", dependencies=[Depends(require_permission(operation, user_dep=OptionalRepositoryUser))])
    async def route(owner: str, repo: str) -> dict[str, str]:
        return {"owner": owner, "repo": repo}

    with TestClient(app) as client:
        assert client.get("/owner/repo").status_code == status
