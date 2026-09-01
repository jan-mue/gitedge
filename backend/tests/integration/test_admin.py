"""Admin page end-to-end tests."""

import pytest
from playwright.sync_api import Page, expect

from tests.integration.conftest import UserCredentials, log_in_user


@pytest.mark.usefixtures("logged_in_superuser")
class TestAdminPageElements:
    """Tests for admin page UI elements."""

    def test_admin_page_is_accessible_and_shows_correct_title(self, page: Page, app_url: str) -> None:
        """Admin page should be accessible and show correct title."""
        page.goto(f"{app_url}/admin")
        expect(page.get_by_role("heading", name="Users")).to_be_visible()
        expect(page.get_by_text("Manage user accounts and permissions")).to_be_visible()

    def test_add_user_button_is_visible(self, page: Page, app_url: str) -> None:
        """Add User button should be visible."""
        page.goto(f"{app_url}/admin")
        expect(page.get_by_role("button", name="Add User")).to_be_visible()


@pytest.mark.usefixtures("logged_in_superuser")
class TestAdminUserManagement:
    """Tests for admin user management functionality."""

    def test_create_new_user_successfully(
        self, page: Page, app_url: str, random_email: str, random_password: str
    ) -> None:
        """Admin should be able to create a new user."""
        page.goto(f"{app_url}/admin")

        full_name = "Test User Admin"

        page.get_by_role("button", name="Add User").click()

        page.get_by_placeholder("Email").fill(random_email)
        page.get_by_placeholder("Full name").fill(full_name)
        page.get_by_placeholder("Password").first.fill(random_password)
        page.get_by_placeholder("Password").last.fill(random_password)

        page.get_by_role("button", name="Save").click()

        expect(page.get_by_text("User created successfully")).to_be_visible()

        expect(page.get_by_role("dialog")).not_to_be_visible()

        # Wait for table to refresh after mutation (may take time for React Query to update)
        user_row = page.get_by_role("row").filter(has_text=random_email)
        expect(user_row).to_be_visible(timeout=15000)

    def test_create_superuser(self, page: Page, app_url: str, random_email: str, random_password: str) -> None:
        """Admin should be able to create a superuser."""
        page.goto(f"{app_url}/admin")

        page.get_by_role("button", name="Add User").click()

        page.get_by_placeholder("Email").fill(random_email)
        page.get_by_placeholder("Password").first.fill(random_password)
        page.get_by_placeholder("Password").last.fill(random_password)
        page.get_by_label("Is superuser?").check()
        page.get_by_label("Is active?").check()

        page.get_by_role("button", name="Save").click()

        expect(page.get_by_text("User created successfully")).to_be_visible()

        expect(page.get_by_role("dialog")).not_to_be_visible()

        # Wait for table to refresh after mutation
        user_row = page.get_by_role("row").filter(has_text=random_email)
        expect(user_row.get_by_text("Superuser")).to_be_visible(timeout=15000)

    def test_edit_user_successfully(self, page: Page, app_url: str, random_email: str, random_password: str) -> None:
        """Admin should be able to edit a user."""
        page.goto(f"{app_url}/admin")

        original_name = "Original Name"
        updated_name = "Updated Name"

        # Create user first
        page.get_by_role("button", name="Add User").click()
        page.get_by_placeholder("Email").fill(random_email)
        page.get_by_placeholder("Full name").fill(original_name)
        page.get_by_placeholder("Password").first.fill(random_password)
        page.get_by_placeholder("Password").last.fill(random_password)
        page.get_by_role("button", name="Save").click()

        expect(page.get_by_text("User created successfully")).to_be_visible()
        expect(page.get_by_role("dialog")).not_to_be_visible()

        # Edit the user (wait for table to refresh)
        user_row = page.get_by_role("row").filter(has_text=random_email)
        expect(user_row).to_be_visible(timeout=15000)
        user_row.get_by_role("button").click()

        page.get_by_role("menuitem", name="Edit User").click()

        page.get_by_placeholder("Full name").fill(updated_name)
        page.get_by_role("button", name="Save").click()

        expect(page.get_by_text("User updated successfully")).to_be_visible()
        expect(page.get_by_text(updated_name)).to_be_visible()

    def test_delete_user_successfully(self, page: Page, app_url: str, random_email: str, random_password: str) -> None:
        """Admin should be able to delete a user."""
        page.goto(f"{app_url}/admin")

        # Create user first
        page.get_by_role("button", name="Add User").click()
        page.get_by_placeholder("Email").fill(random_email)
        page.get_by_placeholder("Password").first.fill(random_password)
        page.get_by_placeholder("Password").last.fill(random_password)
        page.get_by_role("button", name="Save").click()

        expect(page.get_by_text("User created successfully")).to_be_visible()

        expect(page.get_by_role("dialog")).not_to_be_visible()

        # Delete the user (wait for table to refresh)
        user_row = page.get_by_role("row").filter(has_text=random_email)
        expect(user_row).to_be_visible(timeout=15000)
        user_row.get_by_role("button").click()

        page.get_by_role("menuitem", name="Delete User").click()

        page.get_by_role("button", name="Delete").click()

        expect(page.get_by_text("The user was deleted successfully")).to_be_visible()

        expect(page.get_by_role("row").filter(has_text=random_email)).not_to_be_visible()

    def test_cancel_user_creation(self, page: Page, app_url: str) -> None:
        """Admin should be able to cancel user creation."""
        page.goto(f"{app_url}/admin")

        page.get_by_role("button", name="Add User").click()
        page.get_by_placeholder("Email").fill("test@example.com")

        page.get_by_role("button", name="Cancel").click()

        expect(page.get_by_role("dialog")).not_to_be_visible()


@pytest.mark.usefixtures("logged_in_superuser")
class TestAdminFormValidation:
    """Tests for admin form validation."""

    def test_email_is_required_and_must_be_valid(self, page: Page, app_url: str) -> None:
        """Email field should require a valid email."""
        page.goto(f"{app_url}/admin")

        page.get_by_role("button", name="Add User").click()

        page.get_by_placeholder("Email").fill("invalid-email")
        page.get_by_placeholder("Email").blur()

        expect(page.get_by_text("Invalid email address")).to_be_visible()

    def test_password_must_be_at_least_8_characters(self, page: Page, app_url: str, random_email: str) -> None:
        """Password must be at least 8 characters."""
        page.goto(f"{app_url}/admin")

        page.get_by_role("button", name="Add User").click()

        page.get_by_placeholder("Email").fill(random_email)
        page.get_by_placeholder("Password").first.fill("short")
        page.get_by_placeholder("Password").last.fill("short")
        page.get_by_role("button", name="Save").click()

        expect(page.get_by_text("Password must be at least 8 characters")).to_be_visible()

    def test_passwords_must_match(self, page: Page, app_url: str, random_email: str, random_password: str) -> None:
        """Passwords must match."""
        page.goto(f"{app_url}/admin")

        page.get_by_role("button", name="Add User").click()

        page.get_by_placeholder("Email").fill(random_email)
        page.get_by_placeholder("Password").first.fill(random_password)
        page.get_by_placeholder("Password").last.fill("different12345")
        page.get_by_placeholder("Password").last.blur()

        expect(page.get_by_text("The passwords don't match")).to_be_visible()


class TestAdminAccessControl:
    """Tests for admin page access control."""

    def test_non_superuser_cannot_access_admin_page(self, page: Page, app_url: str, test_user: UserCredentials) -> None:
        """Non-superuser should not be able to access admin page."""
        log_in_user(page, app_url, test_user.email, test_user.password)

        page.goto(f"{app_url}/admin")

        expect(page.get_by_role("heading", name="Users")).not_to_be_visible()
        expect(page).not_to_have_url(f"{app_url}/admin")

    @pytest.mark.usefixtures("logged_in_superuser")
    def test_superuser_can_access_admin_page(self, page: Page, app_url: str) -> None:
        """Superuser should be able to access admin page."""
        page.goto(f"{app_url}/admin")

        expect(page.get_by_role("heading", name="Users")).to_be_visible()
