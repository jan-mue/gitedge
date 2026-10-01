"""User settings page end-to-end tests."""

import pytest
from playwright.sync_api import Page, expect

from tests.integration.conftest import (
    FIRST_SUPERUSER,
    FIRST_SUPERUSER_PASSWORD,
    UserCredentials,
    create_user_via_api,
    log_in_user,
    log_out_user,
)

TABS = ["My profile", "Password", "Danger zone"]


class TestUserSettingsElements:
    """Tests for user settings page UI elements."""

    @pytest.fixture(autouse=True)
    def _login_as_superuser(self, page: Page, app_url: str) -> None:
        """Log in as superuser before each test."""
        log_in_user(page, app_url, FIRST_SUPERUSER, FIRST_SUPERUSER_PASSWORD)

    def test_my_profile_tab_is_active_by_default(self, page: Page, app_url: str) -> None:
        """My profile tab should be active by default."""
        page.goto(f"{app_url}/settings")
        expect(page.get_by_role("tab", name="My profile")).to_have_attribute("aria-selected", "true")

    def test_all_tabs_are_visible(self, page: Page, app_url: str) -> None:
        """All tabs should be visible."""
        page.goto(f"{app_url}/settings")
        for tab in TABS:
            expect(page.get_by_role("tab", name=tab)).to_be_visible()


@pytest.mark.usefixtures("logged_in_test_user")
class TestEditUserProfile:
    """Tests for editing user profile."""

    def test_edit_user_name_with_valid_name(self, page: Page, app_url: str) -> None:
        """User should be able to edit their name with a valid name."""
        page.goto(f"{app_url}/settings")
        page.get_by_role("tab", name="My profile").click()

        updated_name = "Test User 2"

        page.get_by_role("button", name="Edit").click()
        page.get_by_label("Full name").fill(updated_name)
        page.get_by_role("button", name="Save").click()

        expect(page.get_by_text("User updated successfully")).to_be_visible()
        expect(page.locator("form").get_by_text(updated_name, exact=True)).to_be_visible()

    def test_edit_user_email_with_invalid_email_shows_error(self, page: Page, app_url: str) -> None:
        """Editing with an invalid email should show an error."""
        page.goto(f"{app_url}/settings")
        page.get_by_role("tab", name="My profile").click()

        page.get_by_role("button", name="Edit").click()
        page.get_by_label("Email").fill("")
        page.locator("body").click()

        expect(page.get_by_text("Invalid email address")).to_be_visible()


class TestEditUserEmail:
    """Tests for editing user email."""

    @pytest.mark.usefixtures("logged_in_test_user")
    def test_edit_user_email_with_valid_email(self, page: Page, app_url: str, random_email: str) -> None:
        """User should be able to edit their email with a valid email."""
        new_email = f"updated_{random_email}"
        page.goto(f"{app_url}/settings")
        page.get_by_role("tab", name="My profile").click()

        page.get_by_role("button", name="Edit").click()
        page.get_by_label("Email").fill(new_email)
        page.get_by_role("button", name="Save").click()

        expect(page.get_by_text("User updated successfully")).to_be_visible()
        expect(page.locator("form").get_by_text(new_email, exact=True)).to_be_visible()


class TestCancelEditActions:
    """Tests for canceling edit actions."""

    def test_cancel_edit_action_restores_original_name(
        self, page: Page, app_url: str, random_email: str, random_password: str
    ) -> None:
        """Canceling edit should restore the original name."""
        user = create_user_via_api(app_url, random_email, random_password)

        log_in_user(page, app_url, random_email, random_password)
        page.goto(f"{app_url}/settings")
        page.get_by_role("tab", name="My profile").click()
        page.get_by_role("button", name="Edit").click()
        page.get_by_label("Full name").fill("Test User")
        page.get_by_role("button", name="Cancel").first.click()

        full_name = user.get("full_name", "Test User")
        expect(page.locator("form").get_by_text(full_name, exact=True)).to_be_visible()

    def test_cancel_edit_action_restores_original_email(
        self, page: Page, app_url: str, logged_in_test_user: UserCredentials, random_email: str
    ) -> None:
        """Canceling edit should restore the original email."""
        page.goto(f"{app_url}/settings")
        page.get_by_role("tab", name="My profile").click()
        page.get_by_role("button", name="Edit").click()
        page.get_by_label("Email").fill(random_email)
        page.get_by_role("button", name="Cancel").first.click()

        expect(page.locator("form").get_by_text(logged_in_test_user.email, exact=True)).to_be_visible()


class TestChangePassword:
    """Tests for changing password."""

    def test_update_password_successfully(
        self, page: Page, app_url: str, logged_in_test_user: UserCredentials, random_password: str
    ) -> None:
        """User should be able to update their password."""
        new_password = f"updated_{random_password}"

        page.goto(f"{app_url}/settings")
        page.get_by_role("tab", name="Password").click()
        page.get_by_test_id("current-password-input").fill(logged_in_test_user.password)
        page.get_by_test_id("new-password-input").fill(new_password)
        page.get_by_test_id("confirm-password-input").fill(new_password)
        page.get_by_role("button", name="Update Password").click()

        expect(page.get_by_text("Password updated successfully")).to_be_visible()

        log_out_user(page, app_url)
        log_in_user(page, app_url, logged_in_test_user.email, new_password)


class TestChangePasswordValidation:
    """Tests for password change validation."""

    def test_update_password_with_weak_password(
        self, page: Page, app_url: str, logged_in_test_user: UserCredentials
    ) -> None:
        """Weak password should show an error."""
        weak_password = "weak"

        page.goto(f"{app_url}/settings")
        page.get_by_role("tab", name="Password").click()
        page.get_by_test_id("current-password-input").fill(logged_in_test_user.password)
        page.get_by_test_id("new-password-input").fill(weak_password)
        page.get_by_test_id("confirm-password-input").fill(weak_password)
        page.get_by_role("button", name="Update Password").click()

        expect(page.get_by_text("Password must be at least 8 characters")).to_be_visible()

    def test_new_password_and_confirmation_do_not_match(
        self, page: Page, app_url: str, logged_in_test_user: UserCredentials, random_password: str
    ) -> None:
        """Mismatched passwords should show an error."""
        page.goto(f"{app_url}/settings")
        page.get_by_role("tab", name="Password").click()
        page.get_by_test_id("current-password-input").fill(logged_in_test_user.password)
        page.get_by_test_id("new-password-input").fill(random_password)
        page.get_by_test_id("confirm-password-input").fill(random_password + "different")
        page.get_by_role("button", name="Update Password").click()

        expect(page.get_by_text("The passwords don't match")).to_be_visible()

    def test_current_and_new_password_are_the_same(
        self, page: Page, app_url: str, logged_in_test_user: UserCredentials
    ) -> None:
        """Same current and new password should show an error."""
        page.goto(f"{app_url}/settings")
        page.get_by_role("tab", name="Password").click()
        page.get_by_test_id("current-password-input").fill(logged_in_test_user.password)
        page.get_by_test_id("new-password-input").fill(logged_in_test_user.password)
        page.get_by_test_id("confirm-password-input").fill(logged_in_test_user.password)
        page.get_by_role("button", name="Update Password").click()

        expect(page.get_by_text("New password cannot be the same as the current one")).to_be_visible()


@pytest.mark.usefixtures("logged_in_superuser")
class TestAppearanceSettings:
    """Tests for appearance settings."""

    def test_appearance_button_is_visible_in_sidebar(self, page: Page, app_url: str) -> None:
        """Appearance button should be visible in sidebar."""
        page.goto(f"{app_url}/settings")
        expect(page.get_by_test_id("theme-button")).to_be_visible()

    def test_user_can_switch_between_theme_modes(self, page: Page, app_url: str) -> None:
        """User should be able to switch between theme modes."""
        page.goto(f"{app_url}/settings")

        page.get_by_test_id("theme-button").click()
        page.get_by_test_id("dark-mode").click()
        expect(page.locator("html")).to_have_class("dark", timeout=5000)

        expect(page.get_by_test_id("dark-mode")).not_to_be_visible()

        page.get_by_test_id("theme-button").click()
        page.get_by_test_id("light-mode").click()
        expect(page.locator("html")).to_have_class("light", timeout=5000)

    def test_selected_mode_is_preserved_across_sessions(self, page: Page, app_url: str) -> None:
        """Selected theme mode should be preserved across sessions."""
        page.goto(f"{app_url}/settings")

        page.get_by_test_id("theme-button").click()
        if page.evaluate("() => document.documentElement.classList.contains('dark')"):
            page.get_by_test_id("light-mode").click()
            page.get_by_test_id("theme-button").click()

        is_light_mode = page.evaluate("() => document.documentElement.classList.contains('light')")
        assert is_light_mode is True

        page.get_by_test_id("theme-button").click()
        page.get_by_test_id("dark-mode").click()
        is_dark_mode = page.evaluate("() => document.documentElement.classList.contains('dark')")
        assert is_dark_mode is True

        log_out_user(page, app_url)
        log_in_user(page, app_url, FIRST_SUPERUSER, FIRST_SUPERUSER_PASSWORD)

        is_dark_mode = page.evaluate("() => document.documentElement.classList.contains('dark')")
        assert is_dark_mode is True
