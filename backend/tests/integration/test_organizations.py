"""End-to-end tests for organizations."""

from __future__ import annotations

from typing import TYPE_CHECKING

from playwright.sync_api import expect

from tests.integration.conftest import FIRST_SUPERUSER, FIRST_SUPERUSER_PASSWORD, log_in_user

if TYPE_CHECKING:
    from playwright.sync_api import Page

SUPERUSER_EMAIL = FIRST_SUPERUSER
SUPERUSER_PASSWORD = FIRST_SUPERUSER_PASSWORD


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
        page.get_by_test_id("new-repo-owner").select_option("test-org")
        page.get_by_test_id("new-repo-name").fill("org-repo")
        page.get_by_test_id("new-repo-submit").click()

        page.wait_for_url(f"{app_url}/test-org/org-repo/src/branch/main")
        expect(page.get_by_test_id("clone-url")).to_have_value(f"{app_url}/test-org/org-repo.git")

        page.goto(f"{app_url}/profile/test-org")
        expect(page.get_by_test_id("user-profile")).to_be_visible(timeout=15000)
        expect(page.get_by_test_id("profile-tab-repositories")).to_contain_text("Repositories (1)")
        expect(page.get_by_test_id("profile-repo-org-repo")).to_be_visible()
        expect(page.get_by_test_id("profile-tab-starred")).to_have_count(0)
