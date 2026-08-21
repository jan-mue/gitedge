from abc import ABC, abstractmethod

import emails
from loguru import logger

from app.config import settings


class EmailClient(ABC):
    @abstractmethod
    def send_email(self, email_to: str, subject: str = "", html_content: str = "") -> None:
        pass


class SMTPClient(EmailClient):
    def __init__(self) -> None:
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
        assert settings.emails_enabled, "no provided configuration for email variables"
        assert settings.EMAILS_FROM_EMAIL  # For type checker
        message = emails.message.Message(
            subject=subject,
            html=html_content,
            mail_from=(settings.EMAILS_FROM_NAME, settings.EMAILS_FROM_EMAIL),
        )
        response = message.send(to=email_to, smtp=self.smtp_options)
        logger.info(f"send email result: {response}")
