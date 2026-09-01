"""Reset password page end-to-end tests."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from playwright.sync_api import expect

from tests.integration.conftest import create_user_via_api, find_last_email, get_email_html, log_in_user

if TYPE_CHECKING:
    from playwright.sync_api import Page


class TestResetPasswordElements:
    """Tests for reset password page UI elements."""

    def test_password_recovery_title_is_visible(self, page: Page, app_url: str) -> None:
        """Password Recovery title should be visible."""
        page.goto(f"{app_url}/recover-password")

        expect(page.get_by_role("heading", name="Password Recovery")).to_be_visible()

    def test_email_input_is_visible_empty_and_editable(self, page: Page, app_url: str) -> None:
        """Email input should be visible, empty, and editable."""
        page.goto(f"{app_url}/recover-password")

        expect(page.get_by_test_id("email-input")).to_be_visible()
        expect(page.get_by_test_id("email-input")).to_have_text("")
        expect(page.get_by_test_id("email-input")).to_be_editable()

    def test_continue_button_is_visible(self, page: Page, app_url: str) -> None:
        """Continue button should be visible."""
        page.goto(f"{app_url}/recover-password")

        expect(page.get_by_role("button", name="Continue")).to_be_visible()


def _get_password_reset_url(page: Page, wrangler_dev_url: str, mailpit_http_url: str, email: str) -> str:
    """Request a password reset and extract the reset URL from the email.

    Args:
        page: The Playwright page.
        wrangler_dev_url: The base URL of the wrangler dev server.
        mailpit_http_url: The Mailpit HTTP API URL.
        email: The user's email address.

    Returns:
        The password reset URL with the correct base URL.
    """
    page.goto(f"{wrangler_dev_url}/recover-password")
    page.get_by_test_id("email-input").fill(email)
    page.get_by_role("button", name="Continue").click()

    # Find the password reset email (allow extra time for email delivery)
    email_data = find_last_email(mailpit_http_url, recipient_filter=email, timeout=30000)

    # Get the email HTML content
    message_id = email_data["ID"]
    html_content = get_email_html(mailpit_http_url, message_id)

    # Extract the reset link from the HTML
    match = re.search(r'href="([^"]*reset-password\?token=[^"]*)"', html_content)
    assert match is not None, "Could not find reset password link in email"
    url = match.group(1)

    # Update the URL to use the correct base URL
    return re.sub(r"https?://[^/]+", wrangler_dev_url, url)


class TestPasswordReset:
    """Tests for password reset functionality."""

    def test_user_can_reset_password_using_link(
        self, page: Page, app_url: str, mailpit_http_url: str, random_email: str, random_password: str
    ) -> None:
        """User should be able to reset password using the email link."""
        email = random_email
        password = random_password
        new_password = password + "2"

        # Create a user via API (more reliable than sign-up flow)
        create_user_via_api(app_url, email, password)

        # Get the password reset URL
        url = _get_password_reset_url(page, app_url, mailpit_http_url, email)

        # Set the new password and confirm it
        page.goto(url)

        page.get_by_test_id("new-password-input").fill(new_password)
        page.get_by_test_id("confirm-password-input").fill(new_password)
        page.get_by_role("button", name="Reset Password").click()
        expect(page.get_by_text("Password updated successfully")).to_be_visible()

        # Check if the user can login with the new password
        log_in_user(page, app_url, email, new_password)

    def test_expired_or_invalid_reset_link(self, page: Page, app_url: str, random_password: str) -> None:
        """Expired or invalid reset link should show an error."""
        invalid_url = f"{app_url}/reset-password?token=invalidtoken"

        page.goto(invalid_url)

        page.get_by_test_id("new-password-input").fill(random_password)
        page.get_by_test_id("confirm-password-input").fill(random_password)
        page.get_by_role("button", name="Reset Password").click()

        expect(page.get_by_text("Invalid token")).to_be_visible()

    def test_weak_new_password_validation(
        self, page: Page, app_url: str, mailpit_http_url: str, random_email: str, random_password: str
    ) -> None:
        """Weak new password should show a validation error."""
        weak_password = "123"

        # Create a user via API (more reliable than sign-up flow)
        create_user_via_api(app_url, random_email, random_password)

        # Get the password reset URL
        url = _get_password_reset_url(page, app_url, mailpit_http_url, random_email)

        # Set a weak new password
        page.goto(url)
        page.get_by_test_id("new-password-input").fill(weak_password)
        page.get_by_test_id("confirm-password-input").fill(weak_password)
        page.get_by_role("button", name="Reset Password").click()

        expect(page.get_by_text("Password must be at least 8 characters")).to_be_visible()
