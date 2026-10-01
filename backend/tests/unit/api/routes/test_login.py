from __future__ import annotations

from typing import TYPE_CHECKING

from app.api.dependencies import get_email_client
from app.config import settings
from app.index import app
from app.schemas.users import UserCreate
from app.utils.email import generate_password_reset_token
from app.utils.security import verify_password
from tests.unit.utils.fakes import FakeEmailClient
from tests.unit.utils.user import user_authentication_headers
from tests.unit.utils.utils import random_email, random_lower_string

if TYPE_CHECKING:
    from fastapi.testclient import TestClient
    from pytest_mock import MockerFixture

    from app.services.crud import CrudService


def test_get_access_token(client: TestClient) -> None:
    login_data = {
        "username": settings.FIRST_SUPERUSER,
        "password": settings.FIRST_SUPERUSER_PASSWORD,
    }
    r = client.post(f"{settings.API_V1_STR}/login/access-token", data=login_data)
    tokens = r.json()
    assert r.status_code == 200
    assert "access_token" in tokens
    assert tokens["access_token"]


def test_get_access_token_incorrect_password(client: TestClient) -> None:
    login_data = {
        "username": settings.FIRST_SUPERUSER,
        "password": "incorrect",
    }
    r = client.post(f"{settings.API_V1_STR}/login/access-token", data=login_data)
    assert r.status_code == 400


def test_use_access_token(client: TestClient, superuser_token_headers: dict[str, str]) -> None:
    r = client.post(
        f"{settings.API_V1_STR}/login/test-token",
        headers=superuser_token_headers,
    )
    result = r.json()
    assert r.status_code == 200
    assert "email" in result


def test_recovery_password(
    client: TestClient, normal_user_token_headers: dict[str, str], mocker: MockerFixture
) -> None:
    # Override email client with fake
    app.dependency_overrides[get_email_client] = FakeEmailClient
    # Mock the email generation since templates don't exist
    mocker.patch(
        "app.api.routes.login.generate_reset_password_email",
        return_value=mocker.MagicMock(subject="Test", html_content="<html>Test</html>"),
    )
    email = "test@example.com"
    r = client.post(
        f"{settings.API_V1_STR}/password-recovery/{email}",
        headers=normal_user_token_headers,
    )
    assert r.status_code == 204


def test_recovery_password_user_not_exits(client: TestClient, normal_user_token_headers: dict[str, str]) -> None:
    email = "jVgQr@example.com"
    r = client.post(
        f"{settings.API_V1_STR}/password-recovery/{email}",
        headers=normal_user_token_headers,
    )
    # Should return 204 (no content) regardless to prevent email enumeration attacks
    assert r.status_code == 204


def test_reset_password(client: TestClient, crud: CrudService) -> None:
    email = random_email()
    password = random_lower_string()
    new_password = random_lower_string()

    crud.create_user(
        UserCreate(
            email=email,
            full_name="Test User",
            password=password,
            is_active=True,
            is_superuser=False,
        )
    )
    token = generate_password_reset_token(email=email)
    headers = user_authentication_headers(client=client, email=email, password=password)
    data = {"new_password": new_password, "token": token}

    r = client.post(
        f"{settings.API_V1_STR}/reset-password/",
        headers=headers,
        json=data,
    )

    assert r.status_code == 204

    user = crud.user_repository.get_by_email(email=email)
    assert user is not None
    assert verify_password(new_password, user.hashed_password)


def test_reset_password_invalid_token(client: TestClient, superuser_token_headers: dict[str, str]) -> None:
    data = {"new_password": "new_test_password", "token": "invalid"}
    r = client.post(
        f"{settings.API_V1_STR}/reset-password/",
        headers=superuser_token_headers,
        json=data,
    )
    response = r.json()

    assert "detail" in response
    assert r.status_code == 400
    assert response["detail"] == "Invalid token"
