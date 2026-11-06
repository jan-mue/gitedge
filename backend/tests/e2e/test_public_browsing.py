"""Public browsing must not trigger session-only requests or login redirects."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from playwright.sync_api import expect

from tests.conftest import FIRST_SUPERUSER, FIRST_SUPERUSER_PASSWORD

if TYPE_CHECKING:
    from playwright.sync_api import Page


def create_repository(page: Page, app_url: str, *, private: bool = False) -> tuple[str, str]:
    """Set up a repository through the API without signing the browser in."""
    api = f"{app_url}/api/v1"
    login = page.request.post(
        f"{api}/login/access-token", form={"username": FIRST_SUPERUSER, "password": FIRST_SUPERUSER_PASSWORD}
    )
    assert login.status == 200
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    owner = page.request.get(f"{api}/users/me", headers=headers).json()["name"]
    name = f"anonymous-{uuid.uuid4().hex[:8]}"
    created = page.request.post(
        f"{api}/repositories/", headers=headers, data={"owner": owner, "name": name, "is_private": private}
    )
    assert created.status == 201
    if not private:
        issue_url = f"{api}/repositories/{owner}/{name}/issues"
        issue = page.request.post(
            issue_url, headers=headers, data={"title": "Public discussion", "body": "Public issue body"}
        )
        assert issue.status == 201
        comment = page.request.post(
            f"{issue_url}/{issue.json()['number']}/comments", headers=headers, data={"body": "Public comment body"}
        )
        assert comment.status == 201
    return owner, name


def test_anonymous_public_repository_browsing(page: Page, app_url: str) -> None:
    owner, name = create_repository(page, app_url)
    unauthorized: list[str] = []
    page.on("response", lambda response: unauthorized.append(response.url) if response.status == 401 else None)
    page.goto(f"{app_url}/{owner}/{name}")
    expect(page.get_by_test_id("empty-repository")).to_be_visible()
    expect(page.get_by_role("link", name="Sign in", exact=True)).to_be_visible()
    assert page.evaluate("localStorage.getItem('access_token')") is None
    for suffix, test_id in [
        ("issues", "tab-issues"),
        ("pulls", "tab-pulls"),
        ("releases", "tab-releases"),
        ("branches", "tab-branches"),
        ("activity", "tab-activity"),
    ]:
        page.get_by_test_id(test_id).first.click()
        expect(page).to_have_url(f"{app_url}/{owner}/{name}/{suffix}")
        expect(page.get_by_test_id("repo-header")).to_be_visible()
    page.goto(f"{app_url}/{owner}/{name}/issues/1")
    expect(page.get_by_text("Public issue body", exact=True)).to_be_visible()
    expect(page.get_by_text("Public comment body", exact=True)).to_be_visible()
    page.goto(f"{app_url}/explore")
    expect(page.get_by_test_id(f"explore-repo-{name}")).to_be_visible()
    page.goto(f"{app_url}/profile/{owner}")
    expect(page.get_by_test_id(f"profile-repo-{name}")).to_be_visible()
    page.goto(f"{app_url}/login")
    page.get_by_role("link", name="Browse public repositories").click()
    expect(page).to_have_url(f"{app_url}/explore")
    expect(page.get_by_test_id(f"explore-repo-{name}")).to_be_visible()
    assert not unauthorized, f"Anonymous browsing made account-only requests: {unauthorized}"


def test_anonymous_private_repository_requires_login(page: Page, app_url: str) -> None:
    owner, name = create_repository(page, app_url, private=True)
    page.goto(f"{app_url}/{owner}/{name}")
    expect(page).to_have_url(f"{app_url}/login")
    expect(page.get_by_test_id("email-input")).to_be_visible()


def test_account_and_repository_management_require_login(page: Page, app_url: str) -> None:
    owner, name = create_repository(page, app_url)
    for path in [
        "settings",
        "notifications",
        "admin",
        "repositories",
        f"{owner}/{name}/settings",
        f"{owner}/{name}/issues/new",
        f"{owner}/{name}/pulls/new",
    ]:
        page.goto(f"{app_url}/{path}")
        expect(page).to_have_url(f"{app_url}/login")
        expect(page.get_by_test_id("email-input")).to_be_visible()
