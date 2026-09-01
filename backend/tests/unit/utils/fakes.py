import logging

from app.clients.email import EmailClient

logger = logging.getLogger(__name__)


class FakeEmailClient(EmailClient):
    def send_email(self, email_to: str, subject: str = "", html_content: str = "") -> None:
        logger.info("Sending email to %s with subject %s and content %s", email_to, subject, html_content)
