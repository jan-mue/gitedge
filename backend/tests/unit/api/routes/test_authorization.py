from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

import pytest

from app.config import settings
from app.entities.authorization import RepositoryCollaborator, Team
from app.entities.organizations import Organization
from app.entities.repositories import Repository
from app.entities.users import User
from app.services.authorization import AuthorizationService
from app.utils.security import create_access_token

if TYPE_CHECKING:
    from fastapi.testclient import TestClient

    from tests.unit.utils.fakes import FakeStores

API = settings.API_V1_STR


def add_user(stores: FakeStores, name: str) -> User:
    user = User(
        name=name,
        lower_name=name,
        email=f"{name}@example.com",
        hashed_password="unused",
        is_active=True,
        is_superuser=False,
    )
    stores.users.persist(user)
    return user


def headers(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user.id, timedelta(minutes=5))}"}


def add_repository(
    stores: FakeStores, user: User | Organization, name: str = "repo", *, private: bool = True
) -> Repository:
    repository = Repository(owner_id=user.id, name=name, is_private=private, default_branch="main")
    stores.repository.persist(repository)
    repository.owner = user
    return repository


def service(stores: FakeStores) -> AuthorizationService:
    return AuthorizationService(stores.authorization, stores.repository, stores.organizations, stores.users)


@pytest.mark.parametrize(
    ("role", "allowed"),
    [
        ("read", {"read"}),
        ("write", {"read", "write"}),
        ("admin", {"read", "write", "admin"}),
        ("owner", {"read", "write", "admin", "owner"}),
    ],
)
async def test_role_hierarchy_is_scoped(fake_stores: FakeStores, role: str, allowed: set[str]) -> None:
    owner = add_user(fake_stores, "owner")
    collaborator = add_user(fake_stores, "collaborator")
    repo = add_repository(fake_stores, owner)
    other = add_repository(fake_stores, owner, "other")
    grant = RepositoryCollaborator(repository_id=repo.id, user_id=collaborator.id, role=role)
    await fake_stores.authorization.save(grant)
    authorization = service(fake_stores)
    for permission in ["read", "write", "admin", "owner"]:
        assert await authorization.can(repo, collaborator, f"repository:{permission}") == (permission in allowed)
        assert not await authorization.can(other, collaborator, f"repository:{permission}")
    await fake_stores.authorization.remove(grant)
    assert not await authorization.can(repo, collaborator)
    assert not await authorization.can(repo, collaborator, "unknown:permission")


@pytest.mark.parametrize(
    "suffix",
    [
        "",
        "/source",
        "/raw",
        "/commits",
        "/issues",
        "/pulls",
        "/releases",
        "/tags",
        "/activity",
        "/stargazers",
        "/watchers",
        "/forks",
    ],
)
def test_private_reads_require_auth_and_grant(client: TestClient, fake_stores: FakeStores, suffix: str) -> None:
    owner = add_user(fake_stores, "owner")
    outsider = add_user(fake_stores, "outsider")
    add_repository(fake_stores, owner)
    url = f"{API}/repositories/owner/repo{suffix}"
    assert client.get(url).status_code == 401
    assert client.get(url, headers=headers(outsider)).status_code == 403


def test_public_read_and_authenticated_creation(client: TestClient, fake_stores: FakeStores) -> None:
    owner = add_user(fake_stores, "owner")
    outsider = add_user(fake_stores, "outsider")
    add_repository(fake_stores, owner, private=False)
    assert client.get(f"{API}/repositories/owner/repo").status_code == 200
    assert client.get(f"{API}/repositories/owner/repo", headers={"Authorization": "Bearer invalid"}).status_code == 401
    body = {"owner": "owner", "name": "new", "is_private": True}
    assert client.post(f"{API}/repositories/", json=body).status_code == 401
    assert client.post(f"{API}/repositories/", json=body, headers=headers(outsider)).status_code == 403
    created = client.post(f"{API}/repositories/", json=body, headers=headers(owner))
    assert created.status_code == 201
    assert created.json()["is_private"] is True
    assert client.get(f"{API}/repositories/owner/new").status_code == 401


async def test_settings_deletion_and_owner_grants(client: TestClient, fake_stores: FakeStores) -> None:
    owner = add_user(fake_stores, "owner")
    admin = add_user(fake_stores, "admin")
    reader = add_user(fake_stores, "reader")
    repo = add_repository(fake_stores, owner)
    await fake_stores.authorization.save(RepositoryCollaborator(repository_id=repo.id, user_id=admin.id, role="admin"))
    await fake_stores.authorization.save(RepositoryCollaborator(repository_id=repo.id, user_id=reader.id, role="read"))
    url = f"{API}/repositories/owner/repo"
    assert client.patch(url, json={"description": "changed"}, headers=headers(reader)).status_code == 403
    assert client.patch(url, json={"description": "changed"}, headers=headers(admin)).status_code == 200
    assert client.delete(url, headers=headers(admin)).status_code == 403
    body = {"user_id": str(reader.id), "role": "owner"}
    assert client.put(f"{url}/collaborators", json=body, headers=headers(admin)).status_code == 403
    response = client.put(f"{url}/collaborators", json=body, headers=headers(owner))
    assert response.status_code == 200
    assert client.delete(f"{url}/collaborators/{response.json()['id']}", headers=headers(admin)).status_code == 403
    assert client.delete(url, headers=headers(reader)).status_code == 204


async def test_team_and_org_admin_inheritance_and_revocation(client: TestClient, fake_stores: FakeStores) -> None:
    admin = add_user(fake_stores, "orgadmin")
    member = add_user(fake_stores, "member")
    outsider = add_user(fake_stores, "outsider")
    response = client.post(f"{API}/organizations/", json={"name": "org"}, headers=headers(admin))
    assert response.status_code == 201
    org = await fake_stores.organizations.get_by_name("org")
    assert org is not None
    repo = add_repository(fake_stores, org)
    url = f"{API}/organizations/org"
    assert client.put(f"{url}/members/{member.id}", json={}, headers=headers(admin)).status_code == 200
    assert client.get(f"{API}/repositories/org/repo", headers=headers(member)).status_code == 403
    team_response = client.post(f"{url}/teams", json={"name": "developers"}, headers=headers(admin))
    team_id = team_response.json()["id"]
    assert client.put(f"{url}/teams/{team_id}/members/{outsider.id}", headers=headers(admin)).status_code == 400
    assert client.put(f"{url}/teams/{team_id}/members/{member.id}", headers=headers(admin)).status_code == 204
    grant_url = f"{API}/repositories/org/repo/collaborators"
    assert client.put(grant_url, json={"team_id": team_id, "role": "write"}, headers=headers(admin)).status_code == 200
    assert await service(fake_stores).can(repo, admin, "repository:owner")
    assert await service(fake_stores).can(repo, member, "repository:write")
    assert client.delete(f"{url}/members/{admin.id}", headers=headers(admin)).status_code == 409
    assert client.put(f"{url}/members/{admin.id}", json={"is_admin": False}, headers=headers(admin)).status_code == 409
    assert client.delete(f"{url}/members/{member.id}", headers=headers(admin)).status_code == 204
    assert not await service(fake_stores).can(repo, member)
    assert client.put(f"{url}/members/{member.id}", json={}, headers=headers(admin)).status_code == 200
    assert not await service(fake_stores).can(repo, member)


async def test_cross_org_teams_and_invalid_subjects(client: TestClient, fake_stores: FakeStores) -> None:
    owner = add_user(fake_stores, "owner")
    org = Organization(name="org", lower_name="org")
    fake_stores.organizations.persist(org)
    repo = add_repository(fake_stores, owner)
    team = Team(organization_id=org.id, name="team")
    await fake_stores.authorization.save(team)
    url = f"{API}/repositories/owner/repo/collaborators"
    for body in [
        {"role": "write"},
        {"role": "write", "user_id": str(owner.id), "team_id": str(team.id)},
        {"user_id": str(owner.id), "role": "root"},
    ]:
        assert client.put(url, json=body, headers=headers(owner)).status_code == 422
    assert client.put(url, json={"team_id": str(team.id), "role": "write"}, headers=headers(owner)).status_code == 400
    assert not await service(fake_stores).can(repo, None)


@pytest.mark.parametrize(
    ("suffix", "private"),
    [
        ("/HEAD", False),
        ("/info/refs?service=git-upload-pack", False),
        ("/HEAD", True),
        ("/git-receive-pack", False),
        ("/info/refs?service=git-receive-pack", False),
    ],
)
def test_git_anonymous_permissions(client: TestClient, fake_stores: FakeStores, suffix: str, *, private: bool) -> None:
    owner = add_user(fake_stores, "owner")
    add_repository(fake_stores, owner, private=private)
    method = client.post if suffix == "/git-receive-pack" else client.get
    response = method(f"{API}/owner/repo.git{suffix}")
    if private or "receive-pack" in suffix:
        assert response.status_code == 401
        assert response.headers["www-authenticate"].startswith("Basic")
    else:
        assert response.status_code == (404 if suffix == "/HEAD" else 200)


async def test_git_push_discovery_requires_write(client: TestClient, fake_stores: FakeStores) -> None:
    owner = add_user(fake_stores, "owner")
    reader = add_user(fake_stores, "reader")
    repo = add_repository(fake_stores, owner)
    grant = RepositoryCollaborator(repository_id=repo.id, user_id=reader.id, role="read")
    await fake_stores.authorization.save(grant)
    url = f"{API}/owner/repo.git/info/refs?service=git-receive-pack"
    assert client.get(url, headers=headers(reader)).status_code == 403
    grant.role = "write"
    await fake_stores.authorization.save(grant)
    assert client.get(url, headers=headers(reader)).status_code == 200


async def test_private_lists_and_starred_profiles(client: TestClient, fake_stores: FakeStores) -> None:
    owner = add_user(fake_stores, "owner")
    outsider = add_user(fake_stores, "outsider")
    add_repository(fake_stores, owner, "public", private=False)
    add_repository(fake_stores, owner, "secret")
    for path in ["/repositories/", "/users/owner/repositories", "/users/owner/starred"]:
        if path.endswith("starred"):
            for name in ["public", "secret"]:
                assert client.put(f"{API}/repositories/owner/{name}/star", headers=headers(owner)).status_code == 200
        public = client.get(API + path)
        assert [item["name"] for item in public.json()["data"]] == ["public"]
        assert public.json()["count"] == 1
        assert client.get(API + path, headers=headers(outsider)).json()["count"] == 1
        assert client.get(API + path, headers=headers(owner)).json()["count"] == 2


async def test_discussion_authors_and_writers(client: TestClient, fake_stores: FakeStores) -> None:
    owner = add_user(fake_stores, "owner")
    author = add_user(fake_stores, "author")
    outsider = add_user(fake_stores, "outsider")
    writer = add_user(fake_stores, "writer")
    repo = add_repository(fake_stores, owner, private=False)
    await fake_stores.authorization.save(RepositoryCollaborator(repository_id=repo.id, user_id=writer.id, role="write"))
    base = f"{API}/repositories/owner/repo"
    issue = client.post(f"{base}/issues", json={"title": "Discussion"}, headers=headers(author))
    assert issue.status_code == 201
    assert client.patch(f"{base}/issues/1", json={"state": "closed"}, headers=headers(outsider)).status_code == 403
    assert client.patch(f"{base}/issues/1", json={"state": "closed"}, headers=headers(author)).status_code == 200
    assert client.patch(f"{base}/issues/1", json={"title": "Maintained"}, headers=headers(writer)).status_code == 200
    comment = client.post(f"{base}/issues/1/comments", json={"body": "Reply"}, headers=headers(author)).json()
    comment_url = f"{API}/comments/{comment['id']}"
    assert client.patch(comment_url, json={"body": "Changed"}, headers=headers(outsider)).status_code == 403
    assert client.patch(comment_url, json={"body": "Changed"}, headers=headers(writer)).status_code == 200
    repo.is_private = True
    assert client.delete(comment_url, headers=headers(author)).status_code == 403
    assert client.delete(comment_url, headers=headers(writer)).status_code == 204
    pull = client.post(f"{base}/pulls", json={"title": "PR", "head_branch": "feature"}, headers=headers(writer)).json()
    pull_url = f"{base}/pulls/{pull['number']}"
    grant = RepositoryCollaborator(repository_id=repo.id, user_id=author.id, role="read")
    await fake_stores.authorization.save(grant)
    assert client.patch(pull_url, json={"state": "merged"}, headers=headers(author)).status_code == 403
    assert client.patch(pull_url, json={"state": "merged"}, headers=headers(writer)).status_code == 200


async def test_drafts_and_revoked_stars_do_not_leak(client: TestClient, fake_stores: FakeStores) -> None:
    owner = add_user(fake_stores, "owner")
    reader = add_user(fake_stores, "reader")
    repo = add_repository(fake_stores, owner)
    grant = RepositoryCollaborator(repository_id=repo.id, user_id=reader.id, role="read")
    await fake_stores.authorization.save(grant)
    base = f"{API}/repositories/owner/repo"
    assert client.put(f"{base}/star", headers=headers(reader)).status_code == 200
    assert (
        client.post(
            f"{base}/releases", json={"tag_name": "draft", "is_draft": True}, headers=headers(owner)
        ).status_code
        == 201
    )
    assert client.get(f"{base}/releases", headers=headers(reader)).json()["count"] == 0
    assert client.get(f"{base}/releases?include_drafts=true", headers=headers(reader)).status_code == 403
    assert client.get(f"{base}/releases/draft", headers=headers(reader)).status_code == 403
    assert client.get(f"{base}/releases/draft", headers=headers(owner)).status_code == 200
    assert client.post(f"{base}/issues", json={"title": "Secret"}, headers=headers(owner)).status_code == 201
    assert client.get(f"{API}/users/me/feed", headers=headers(reader)).json()["count"] > 0
    await fake_stores.authorization.remove(grant)
    assert client.get(f"{API}/users/me/starred", headers=headers(reader)).json()["count"] == 0
    assert client.get(f"{API}/users/me/feed", headers=headers(reader)).json()["count"] == 0
    assert client.get(f"{API}/users/reader/starred").json()["count"] == 0


def test_git_basic_credentials(client: TestClient, fake_stores: FakeStores) -> None:
    owner = next(iter(fake_stores.users.items.values()))
    add_repository(fake_stores, owner)
    url = f"{API}/{owner.name}/repo.git/info/refs?service=git-upload-pack"
    assert client.get(url, auth=(owner.name, settings.FIRST_SUPERUSER_PASSWORD)).status_code == 200
    assert client.get(url, auth=(owner.name, "wrong-password")).status_code == 401
    assert client.get(url, headers={"Authorization": "Basic invalid"}).status_code == 401
    owner.is_active = False
    assert client.get(url, headers=headers(owner)).status_code == 403


def test_current_privacy_and_permissions(client: TestClient, fake_stores: FakeStores) -> None:
    owner = add_user(fake_stores, "owner")
    repo = add_repository(fake_stores, owner, private=False)
    url = f"{API}/repositories/owner/repo"
    assert client.get(url).headers["cache-control"].startswith("public")
    assert client.get(f"{url}/permissions").json() == {"read": True, "write": False, "admin": False, "owner": False}
    assert client.get(f"{url}/permissions", headers=headers(owner)).json() == {
        "read": True,
        "write": True,
        "admin": True,
        "owner": True,
    }
    repo.is_private = True
    assert client.get(url).status_code == 401
    assert client.get(url, headers=headers(owner)).headers["cache-control"] == "private, no-store"
