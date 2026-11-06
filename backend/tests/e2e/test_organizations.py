"""End-to-end tests for organizations."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from playwright.sync_api import expect

from tests.conftest import FIRST_SUPERUSER, FIRST_SUPERUSER_PASSWORD
from tests.e2e.conftest import log_in_user

if TYPE_CHECKING:
    from playwright.sync_api import Page

    from tests.conftest import UserCredentials

SUPERUSER_EMAIL = FIRST_SUPERUSER
SUPERUSER_PASSWORD = FIRST_SUPERUSER_PASSWORD


@pytest.mark.usefixtures("logged_in_superuser")
def test_membership_changes_update_repository_relationships(
    page: Page, app_url: str, test_user: UserCredentials
) -> None:
    """The members table changes real Casbin access immediately, including demotion and removal."""
    api = f"{app_url}/api/v1"
    session = {"Authorization": f"Bearer {page.evaluate('localStorage.getItem("access_token")')}"}
    login = page.request.post(
        f"{api}/login/access-token", form={"username": test_user.email, "password": test_user.password}
    )
    assert login.status == 200
    viewer = {"Authorization": f"Bearer {login.json()['access_token']}"}
    identity = page.request.get(f"{api}/users/me", headers=viewer).json()
    organization = "relationship-browser-org"
    assert page.request.post(f"{api}/organizations/", headers=session, data={"name": organization}).status == 201
    assert (
        page.request.post(
            f"{api}/repositories/", headers=session, data={"owner": organization, "name": "private", "is_private": True}
        ).status
        == 201
    )
    repository = f"{api}/repositories/{organization}/private"
    assert page.request.get(repository, headers=viewer).status == 403
    page.goto(f"{app_url}/profile/{organization}")
    page.get_by_role("button", name="Members", exact=True).click()
    page.get_by_role("button", name="Add people", exact=True).click()
    dialog = page.get_by_role("dialog")
    dialog.get_by_label("Search by username, full name, or email").fill(identity["name"])
    dialog.get_by_role("button").filter(has_text=identity["name"]).click()
    dialog.get_by_role("button", name="Add to organization", exact=True).click()
    expect(dialog).not_to_be_visible()
    role = page.get_by_role("combobox", name=f"Role for {identity['name']}", exact=True)
    expect(role).to_be_visible()
    assert page.request.get(repository, headers=viewer).status == 403
    member_url = f"{api}/organizations/{organization}/members/{identity['id']}"
    for value, status in [("Admin", 200), ("Member", 403)]:
        role.click()
        with page.expect_response(
            lambda response: response.url == member_url and response.request.method == "PUT"
        ) as updated:
            page.get_by_role("option", name=value, exact=True).click()
        assert updated.value.status == 200
        expect(role).to_have_text(value)
        assert page.request.get(repository, headers=viewer).status == status
    page.get_by_role("button", name=f"Remove {identity['name']}", exact=True).click()
    with page.expect_response(
        lambda response: response.url == member_url and response.request.method == "DELETE"
    ) as removed:
        page.get_by_role("button", name="Remove access", exact=True).click()
    assert removed.value.status == 204
    expect(role).not_to_be_visible()
    assert page.request.get(repository, headers=viewer).status == 403


class TestOrganizations:
    """Test creating organizations and organization-owned repositories."""

    def test_create_organization_and_repository(self, app_url: str, page: Page) -> None:
        """An organization can be created and can own repositories.

        Args:
            app_url: Base URL of the GitEdge frontend.
            page: Playwright page.
        """
        log_in_user(page, app_url, SUPERUSER_EMAIL, SUPERUSER_PASSWORD)

        page.get_by_test_id("create-menu").click()
        page.get_by_role("menuitem", name="New Organization").click()
        expect(page.get_by_role("dialog", name="New Organization")).to_be_visible()
        page.get_by_test_id("new-org-name").fill("test-org")
        page.get_by_test_id("new-org-submit").click()
        expect(page.get_by_role("dialog", name="New Organization")).to_be_hidden()

        page.get_by_test_id("create-menu").click()
        page.get_by_role("menuitem", name="New Repository").click()
        expect(page.get_by_role("dialog", name="New Repository")).to_be_visible()
        page.get_by_test_id("new-repo-owner").click()
        page.get_by_role("option", name="test-org", exact=True).click()
        page.get_by_test_id("new-repo-name").fill("org-repo")
        page.get_by_test_id("new-repo-submit").click()

        page.wait_for_url(f"{app_url}/test-org/org-repo/src/branch/main")
        expect(page.get_by_test_id("clone-url")).to_have_value(f"{app_url}/test-org/org-repo.git")

        page.goto(f"{app_url}/profile/test-org")
        expect(page.get_by_test_id("user-profile")).to_be_visible(timeout=15000)
        expect(page.get_by_test_id("profile-tab-repositories")).to_contain_text("Repositories (1)")
        expect(page.get_by_test_id("profile-repo-org-repo")).to_be_visible()
        expect(page.get_by_test_id("profile-tab-starred")).to_have_count(0)
