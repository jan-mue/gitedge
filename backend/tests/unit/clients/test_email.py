"""The email transport exposes delivery failures as a domain error."""

from smtplib import SMTPException
from typing import TYPE_CHECKING

import pytest

from app.clients.email import SMTPClient
from app.config import settings
from app.exceptions import EmailDeliveryError

if TYPE_CHECKING:
    from pytest_mock import MockerFixture


@pytest.mark.parametrize("failure", [SMTPException("SMTP disconnected"), OSError("Connection refused")])
def test_transport_failure_is_normalized(mocker: MockerFixture, failure: Exception) -> None:
    mocker.patch.object(settings, "SMTP_HOST", "smtp.example.test")
    mocker.patch.object(settings, "EMAILS_FROM_EMAIL", "noreply@example.test")
    message = mocker.patch("app.clients.email.Message")
    message.return_value.send.side_effect = failure
    with pytest.raises(EmailDeliveryError, match="SMTP transport failed") as caught:
        SMTPClient().send_email("recipient@example.com", "Subject", "Body")
    assert caught.value.__cause__ is failure


def test_missing_configuration_raises_delivery_error(mocker: MockerFixture) -> None:
    mocker.patch.object(settings, "SMTP_HOST", None)
    with pytest.raises(EmailDeliveryError, match="configuration"):
        SMTPClient().send_email("recipient@example.com", "Subject", "Body")
