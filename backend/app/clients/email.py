"""Email client for sending emails via SMTP."""

import logging
from abc import ABC, abstractmethod

from emails.message import Message

from app.config import settings

logger = logging.getLogger(__name__)


class EmailClient(ABC):
    """Abstract base class for email clients."""

    @abstractmethod
    def send_email(self, email_to: str, subject: str = "", html_content: str = "") -> None:
        """Send an email.

        Args:
            email_to: Recipient email address.
            subject: Email subject.
            html_content: Email body in HTML format.
        """


class SMTPClient(EmailClient):
    """SMTP email client implementation."""

    def __init__(self) -> None:
        """Initialize the SMTP client with settings."""
        self.smtp_options = {"host": settings.SMTP_HOST, "port": settings.SMTP_PORT}
        if settings.SMTP_TLS:
            self.smtp_options["tls"] = True
        elif settings.SMTP_SSL:
            self.smtp_options["ssl"] = True
        if settings.SMTP_USER:
            self.smtp_options["user"] = settings.SMTP_USER
        if settings.SMTP_PASSWORD:
            self.smtp_options["password"] = settings.SMTP_PASSWORD

    def send_email(self, email_to: str, subject: str = "", html_content: str = "") -> None:
        """Send an email via SMTP.

        Args:
            email_to: Recipient email address.
            subject: Email subject.
            html_content: Email body in HTML format.

        Raises:
            RuntimeError: If email settings are not configured.
        """
        from_name = settings.EMAILS_FROM_NAME
        from_email = settings.EMAILS_FROM_EMAIL
        if settings.SMTP_HOST is None or from_name is None or from_email is None:
            raise RuntimeError("No provided configuration for email variables")
        message = Message(
            subject=subject,
            html=html_content,
            mail_from=(from_name, str(from_email)),
        )
        response = message.send(to=email_to, smtp=self.smtp_options)
        logger.info("send email result: %s", response)
