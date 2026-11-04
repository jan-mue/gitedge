"""Best-effort email delivery for operations whose success does not depend on SMTP."""

import logging
from typing import TYPE_CHECKING

from app.exceptions import EmailDeliveryError

if TYPE_CHECKING:
    from app.clients.email import EmailClient

logger = logging.getLogger(__name__)


class EmailService:
    """Keep optional email failures from undoing an already successful operation."""

    def __init__(self, client: EmailClient) -> None:
        """Bind the email transport."""
        self.client = client

    def send_best_effort(self, email_to: str, subject: str, html_content: str) -> None:
        """Log expected delivery failures; propagate unexpected programming errors."""
        try:
            self.client.send_email(email_to, subject, html_content)
        except EmailDeliveryError:
            logger.exception("Email delivery failed")
