from loguru import logger

from app.clients.email import EmailClient


class FakeEmailClient(EmailClient):
    def send_email(
        self, email_to: str, subject: str = "", html_content: str = ""
    ) -> None:
        logger.info(
            f"Sending email to {email_to} with subject {subject} and content {html_content}"
        )
