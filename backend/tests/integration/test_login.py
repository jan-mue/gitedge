"""Login page end-to-end tests."""

import pytest
from playwright.sync_api import Page, expect

from tests.integration.conftest import FIRST_SUPERUSER, FIRST_SUPERUSER_PASSWORD


@pytest.fixture
def clean_storage_state(page: Page) -> Page:
    """Clear storage state for tests that need a fresh session."""
    page.context.clear_cookies()
    page.evaluate("() => localStorage.clear()")
    return page


class TestLoginInputs:
    """Tests for login page input elements."""

    def test_email_input_is_visible_empty_and_editable(self, page: Page, app_url: str) -> None:
        """Email input should be visible, empty, and editable."""
        page.goto(f"{app_url}/login")

        email_input = page.get_by_test_id("email-input")
        expect(email_input).to_be_visible()
        expect(email_input).to_have_text("")
        expect(email_input).to_be_editable()

    def test_password_input_is_visible_empty_and_editable(self, page: Page, app_url: str) -> None:
        """Password input should be visible, empty, and editable."""
        page.goto(f"{app_url}/login")

        password_input = page.get_by_test_id("password-input")
        expect(password_input).to_be_visible()
        expect(password_input).to_have_text("")
        expect(password_input).to_be_editable()


class TestLoginElements:
    """Tests for login page UI elements."""

    def test_log_in_button_is_visible(self, page: Page, app_url: str) -> None:
        """Log In button should be visible."""
        page.goto(f"{app_url}/login")

        expect(page.get_by_role("button", name="Log In")).to_be_visible()

    def test_forgot_password_link_is_visible(self, page: Page, app_url: str) -> None:
        """Forgot Password link should be visible."""
        page.goto(f"{app_url}/login")

        expect(page.get_by_role("link", name="Forgot your password?")).to_be_visible()


class TestLoginAuthentication:
    """Tests for login authentication functionality."""

    def test_log_in_with_valid_email_and_password(self, page: Page, app_url: str) -> None:
        """User should be able to log in with valid credentials."""
        page.goto(f"{app_url}/login")

        page.get_by_test_id("email-input").fill(FIRST_SUPERUSER)
        page.get_by_test_id("password-input").fill(FIRST_SUPERUSER_PASSWORD)
        page.get_by_role("button", name="Log In").click()

        page.wait_for_url(f"{app_url}/")

        expect(page.get_by_text("Welcome back, nice to see you again!")).to_be_visible()

    def test_log_in_with_invalid_email(self, page: Page, app_url: str) -> None:
        """Invalid email should show an error message."""
        page.goto(f"{app_url}/login")

        page.get_by_test_id("email-input").fill("invalidemail")
        page.get_by_test_id("password-input").fill(FIRST_SUPERUSER_PASSWORD)
        page.get_by_role("button", name="Log In").click()

        expect(page.get_by_text("Invalid email address")).to_be_visible()

    def test_log_in_with_invalid_password(self, page: Page, app_url: str, random_password: str) -> None:
        """Invalid password should show an error message."""
        page.goto(f"{app_url}/login")
        page.get_by_test_id("email-input").fill(FIRST_SUPERUSER)
        page.get_by_test_id("password-input").fill(random_password)
        page.get_by_role("button", name="Log In").click()

        expect(page.get_by_text("Incorrect email or password")).to_be_visible()


class TestLogout:
    """Tests for logout functionality."""

    def test_successful_log_out(self, page: Page, app_url: str) -> None:
        """User should be able to log out successfully."""
        page.goto(f"{app_url}/login")

        page.get_by_test_id("email-input").fill(FIRST_SUPERUSER)
        page.get_by_test_id("password-input").fill(FIRST_SUPERUSER_PASSWORD)
        page.get_by_role("button", name="Log In").click()

        page.wait_for_url(f"{app_url}/")

        expect(page.get_by_text("Welcome back, nice to see you again!")).to_be_visible()

        # Wait for user menu to be visible before clicking (longer timeout for sidebar to load)
        user_menu = page.get_by_test_id("user-menu")
        expect(user_menu).to_be_visible(timeout=30000)
        user_menu.click()
        page.get_by_role("menuitem", name="Log out").click()
        page.wait_for_url(f"{app_url}/login")

    @pytest.mark.usefixtures("logged_in_superuser")
    def test_logged_out_user_cannot_access_protected_routes(self, page: Page, app_url: str) -> None:
        """Logged out user should be redirected to login when accessing protected routes."""
        # Log out - wait for user menu to be visible first (longer timeout for sidebar to load)
        user_menu = page.get_by_test_id("user-menu")
        expect(user_menu).to_be_visible(timeout=30000)
        user_menu.click()
        page.get_by_role("menuitem", name="Log out").click()
        page.wait_for_url(f"{app_url}/login")

        page.goto(f"{app_url}/settings")
        page.wait_for_url(f"{app_url}/login")

    def test_redirects_to_login_when_token_is_wrong(self, page: Page, app_url: str) -> None:
        """User with invalid token should be redirected to login."""
        page.goto(f"{app_url}/settings")
        page.evaluate("() => localStorage.setItem('access_token', 'invalid_token')")
        page.goto(f"{app_url}/settings")
        page.wait_for_url(f"{app_url}/login")
        expect(page).to_have_url(f"{app_url}/login")
