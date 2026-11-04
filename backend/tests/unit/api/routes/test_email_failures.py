"""SMTP failures must not change account operations or expose account existence."""

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
    mocker.patch.object(settings, "SMTP_HOST", "smtp.example.test")
    mocker.patch.object(settings, "EMAILS_FROM_EMAIL", "noreply@example.test")
    for module, function in [
        ("app.services.crud", "generate_reset_password_email"),
        ("app.services.crud", "generate_new_account_email"),
        ("app.api.routes.utils", "generate_test_email"),
    ]:
        mocker.patch(f"{module}.{function}", return_value=EmailData(subject="Test", html_content="Test"))
    yield email
    app.dependency_overrides.pop(get_email_client, None)


@pytest.mark.usefixtures("superuser_token_headers")
def test_recovery_does_not_reveal_existing_account_when_smtp_rejects(
    client: TestClient, rejected_email: MockType
) -> None:
    existing = client.post(f"{settings.API_V1_STR}/password-recovery/{settings.FIRST_SUPERUSER}")
    missing = client.post(f"{settings.API_V1_STR}/password-recovery/not-an-account@example.com")
    assert existing.status_code == missing.status_code == 204
    assert existing.content == missing.content == b""
    rejected_email.send_email.assert_called_once()


def test_account_creation_succeeds_when_welcome_email_is_rejected(
    client: TestClient, superuser_token_headers: dict[str, str], rejected_email: MockType
) -> None:
    response = client.post(
        f"{settings.API_V1_STR}/users/",
        headers=superuser_token_headers,
        json={"email": "welcome-rejected@example.com", "password": "secure_password123", "name": "welcome-rejected"},
    )
    assert response.status_code == 200
    assert response.json()["email"] == "welcome-rejected@example.com"
    login = client.post(
        f"{settings.API_V1_STR}/login/access-token",
        data={"username": "welcome-rejected@example.com", "password": "secure_password123"},
    )
    assert login.status_code == 200
    rejected_email.send_email.assert_called_once()


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


@pytest.mark.usefixtures("superuser_token_headers")
def test_optional_email_does_not_swallow_programming_errors(client: TestClient, rejected_email: MockType) -> None:
    rejected_email.send_email.side_effect = RuntimeError("Unexpected programming error")
    with pytest.raises(RuntimeError, match="Unexpected programming error"):
        client.post(f"{settings.API_V1_STR}/password-recovery/{settings.FIRST_SUPERUSER}")
