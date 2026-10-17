"""Sign-up page end-to-end tests."""

from playwright.sync_api import Page, expect


class TestSignUpInputs:
    """Tests for sign-up page input elements."""

    def test_full_name_input_is_visible_empty_and_editable(self, page: Page, app_url: str) -> None:
        """Full name input should be visible, empty, and editable."""
        page.goto(f"{app_url}/signup")

        full_name_input = page.get_by_test_id("full-name-input")
        expect(full_name_input).to_be_visible()
        expect(full_name_input).to_have_text("")
        expect(full_name_input).to_be_editable()

    def test_email_input_is_visible_empty_and_editable(self, page: Page, app_url: str) -> None:
        """Email input should be visible, empty, and editable."""
        page.goto(f"{app_url}/signup")

        email_input = page.get_by_test_id("email-input")
        expect(email_input).to_be_visible()
        expect(email_input).to_have_text("")
        expect(email_input).to_be_editable()

    def test_password_input_is_visible_empty_and_editable(self, page: Page, app_url: str) -> None:
        """Password input should be visible, empty, and editable."""
        page.goto(f"{app_url}/signup")

        password_input = page.get_by_test_id("password-input")
        expect(password_input).to_be_visible()
        expect(password_input).to_have_text("")
        expect(password_input).to_be_editable()

    def test_confirm_password_input_is_visible_empty_and_editable(self, page: Page, app_url: str) -> None:
        """Confirm password input should be visible, empty, and editable."""
        page.goto(f"{app_url}/signup")

        confirm_password_input = page.get_by_test_id("confirm-password-input")
        expect(confirm_password_input).to_be_visible()
        expect(confirm_password_input).to_have_text("")
        expect(confirm_password_input).to_be_editable()


class TestSignUpElements:
    """Tests for sign-up page UI elements."""

    def test_sign_up_button_is_visible(self, page: Page, app_url: str) -> None:
        """Sign Up button should be visible."""
        page.goto(f"{app_url}/signup")

        expect(page.get_by_role("button", name="Sign Up")).to_be_visible()

    def test_log_in_link_is_visible(self, page: Page, app_url: str) -> None:
        """Log In link should be visible."""
        page.goto(f"{app_url}/signup")

        expect(page.get_by_role("link", name="Log In")).to_be_visible()


def _fill_signup_form(
    page: Page, full_name: str, email: str, password: str, confirm_password: str | None = None
) -> None:
    """Fill in the sign-up form.

    Args:
        page: The Playwright page.
        full_name: The user's full name.
        email: The user's email.
        password: The user's password.
        confirm_password: The password confirmation (defaults to password if None).
    """
    page.get_by_test_id("full-name-input").fill(full_name)
    page.get_by_test_id("email-input").fill(email)
    page.get_by_test_id("password-input").fill(password)
    page.get_by_test_id("confirm-password-input").fill(confirm_password if confirm_password is not None else password)
    page.get_by_role("button", name="Sign Up").click()


class TestSignUpValidation:
    """Tests for sign-up form validation."""

    def test_sign_up_with_valid_data(self, page: Page, app_url: str, random_email: str, random_password: str) -> None:
        """User should be able to sign up with valid name, email, and password."""
        full_name = "Test User"

        page.goto(f"{app_url}/signup")
        _fill_signup_form(page, full_name, random_email, random_password)

    def test_sign_up_with_invalid_email(self, page: Page, app_url: str) -> None:
        """Invalid email should show an error message."""
        page.goto(f"{app_url}/signup")
        _fill_signup_form(page, "Playwright Test", "invalid-email", "password123")

        expect(page.get_by_text("Invalid email address")).to_be_visible()

    def test_sign_up_with_existing_email(
        self, page: Page, app_url: str, random_email: str, random_password: str
    ) -> None:
        """Signing up with an existing email should show an error message."""
        full_name = "Test User"

        page.goto(f"{app_url}/signup")
        _fill_signup_form(page, full_name, random_email, random_password)

        page.goto(f"{app_url}/signup")
        _fill_signup_form(page, full_name, random_email, random_password)

        expect(page.get_by_text("The user with this email already exists in the system")).to_be_visible()

    def test_sign_up_with_weak_password(self, page: Page, app_url: str, random_email: str) -> None:
        """Weak password should show an error message."""
        full_name = "Test User"
        password = "weak"

        page.goto(f"{app_url}/signup")
        _fill_signup_form(page, full_name, random_email, password)

        expect(page.get_by_text("Password must be at least 8 characters")).to_be_visible()

    def test_sign_up_with_mismatched_passwords(
        self, page: Page, app_url: str, random_email: str, random_password: str
    ) -> None:
        """Mismatched passwords should show an error message."""
        full_name = "Test User"
        email = random_email
        password = random_password
        password2 = password + "2"

        page.goto(f"{app_url}/signup")
        _fill_signup_form(page, full_name, email, password, confirm_password=password2)

        expect(page.get_by_text("The passwords don't match")).to_be_visible()

    def test_sign_up_with_missing_full_name(
        self, page: Page, app_url: str, random_email: str, random_password: str
    ) -> None:
        """Missing full name should show an error message."""
        page.goto(f"{app_url}/signup")
        _fill_signup_form(page, "", random_email, random_password)

        expect(page.get_by_text("Full Name is required")).to_be_visible()

    def test_sign_up_with_missing_email(self, page: Page, app_url: str, random_password: str) -> None:
        """Missing email should show an error message."""
        page.goto(f"{app_url}/signup")
        _fill_signup_form(page, "Test User", "", random_password)

        expect(page.get_by_text("Invalid email address")).to_be_visible()

    def test_sign_up_with_missing_password(self, page: Page, app_url: str, random_email: str) -> None:
        """Missing password should show an error message."""
        page.goto(f"{app_url}/signup")
        _fill_signup_form(page, "", random_email, "")

        expect(page.get_by_text("Password is required")).to_be_visible()
