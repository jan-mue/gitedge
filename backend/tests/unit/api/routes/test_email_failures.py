"""Email diagnostics report transport failures through the global handler."""

from typing import TYPE_CHECKING

import pytest

from app.api.dependencies import get_email_client
from app.clients.email import EmailClient
from app.config import settings
from app.exceptions import EmailDeliveryError
from app.index import app
from app.utils.email import EmailData

if TYPE_CHECKING:
    from collections.abc import Generator

    from fastapi.testclient import TestClient
    from pytest_mock import MockerFixture, MockType


@pytest.fixture
def rejected_email(mocker: MockerFixture) -> Generator[MockType]:
    email = mocker.Mock(spec=EmailClient)
    email.send_email.side_effect = EmailDeliveryError("SMTP delivery failed with status 550")
    app.dependency_overrides[get_email_client] = lambda: email
    mocker.patch(
        "app.api.routes.utils.generate_test_email", return_value=EmailData(subject="Test", html_content="Test")
    )
    yield email
    app.dependency_overrides.pop(get_email_client, None)


def test_email_diagnostics_reports_delivery_failure(
    client: TestClient, superuser_token_headers: dict[str, str], rejected_email: MockType
) -> None:
    response = client.post(
        f"{settings.API_V1_STR}/utils/test-email/",
        headers=superuser_token_headers,
        params={"email_to": "recipient@example.com"},
    )
    assert response.status_code == 500
    assert response.json() == {"detail": "Email delivery failed"}

    rejected_email.send_email.assert_called_once()
