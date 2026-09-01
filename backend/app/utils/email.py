"""Email generation utilities."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from jinja2 import Template
from jwt.exceptions import InvalidTokenError

from app.config import settings
from app.constants import RESOURCES_DIR
from app.utils import security


@dataclass
class EmailData:
    """Data class for email content."""

    html_content: str
    subject: str


def render_email_template(*, template_name: str, context: dict[str, Any]) -> str:
    """Render an email template with the given context.

    Args:
        template_name: Name of the template file in email-templates.
        context: Dictionary of variables to pass to the template.

    Returns:
        Rendered HTML content.
    """
    template_str = (RESOURCES_DIR / "email-templates" / template_name).read_text()
    return Template(template_str).render(context)


def generate_test_email(email_to: str) -> EmailData:
    """Generate a test email.

    Args:
        email_to: Recipient email address.

    Returns:
        EmailData with subject and HTML content.
    """
    project_name = settings.PROJECT_NAME
    subject = f"{project_name} - Test email"
    html_content = render_email_template(
        template_name="test_email.html",
        context={"project_name": settings.PROJECT_NAME, "email": email_to},
    )
    return EmailData(html_content=html_content, subject=subject)


def generate_reset_password_email(email_to: str, email: str, token: str) -> EmailData:
    """Generate a password reset email.

    Args:
        email_to: Recipient email address.
        email: User's email for display.
        token: Password reset token.

    Returns:
        EmailData with subject and HTML content.
    """
    project_name = settings.PROJECT_NAME
    subject = f"{project_name} - Password recovery for user {email}"
    link = f"{settings.FRONTEND_HOST}/reset-password?token={token}"
    html_content = render_email_template(
        template_name="reset_password.html",
        context={
            "project_name": settings.PROJECT_NAME,
            "username": email,
            "email": email_to,
            "valid_hours": settings.EMAIL_RESET_TOKEN_EXPIRE_HOURS,
            "link": link,
        },
    )
    return EmailData(html_content=html_content, subject=subject)


def generate_new_account_email(email_to: str, username: str, password: str) -> EmailData:
    """Generate a new account welcome email.

    Args:
        email_to: Recipient email address.
        username: New user's username.
        password: New user's password.

    Returns:
        EmailData with subject and HTML content.
    """
    project_name = settings.PROJECT_NAME
    subject = f"{project_name} - New account for user {username}"
    html_content = render_email_template(
        template_name="new_account.html",
        context={
            "project_name": settings.PROJECT_NAME,
            "username": username,
            "password": password,
            "email": email_to,
            "link": settings.FRONTEND_HOST,
        },
    )
    return EmailData(html_content=html_content, subject=subject)


def generate_password_reset_token(email: str) -> str:
    """Generate a password reset token.

    Args:
        email: User's email address.

    Returns:
        JWT token for password reset.
    """
    delta = timedelta(hours=settings.EMAIL_RESET_TOKEN_EXPIRE_HOURS)
    now = datetime.now(UTC)
    expires = now + delta
    exp = expires.timestamp()
    return jwt.encode(
        {"exp": exp, "nbf": now, "sub": email},
        settings.SECRET_KEY,
        algorithm=security.ALGORITHM,
    )


def verify_password_reset_token(token: str) -> str | None:
    """Verify a password reset token.

    Args:
        token: The JWT token to verify.

    Returns:
        The email address if valid, None otherwise.
    """
    try:
        decoded_token = jwt.decode(token, settings.SECRET_KEY, algorithms=[security.ALGORITHM])
        return str(decoded_token["sub"])
    except InvalidTokenError:
        return None
