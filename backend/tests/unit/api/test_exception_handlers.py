"""Expected application failures keep their public HTTP contracts."""

from typing import TYPE_CHECKING

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_repository_store
from app.config import settings
from app.exceptions import (
    AuthenticationError,
    ConflictError,
    InsufficientTokenScopeError,
    InvalidInputError,
    InvalidPersonalAccessTokenError,
    PayloadTooLargeError,
    PermissionDeniedError,
    RateLimitError,
    RepositoryNotFoundError,
    ServiceUnavailableError,
    TokenAuthenticationLimitError,
    TokenIssuanceError,
    TokenNotFoundError,
    TokenRevokedError,
    UnprocessableInputError,
)
from app.index import app

if TYPE_CHECKING:
    from app.exceptions import ApplicationError


@pytest.mark.parametrize(
    ("error", "code", "headers"),
    [
        (InvalidInputError("Invalid branch name"), 400, {}),
        (AuthenticationError(), 401, {"www-authenticate": "Bearer"}),
        (AuthenticationError(challenge='Basic realm="GitEdge"'), 401, {"www-authenticate": 'Basic realm="GitEdge"'}),
        (InvalidPersonalAccessTokenError(), 401, {"www-authenticate": 'Basic realm="GitEdge"'}),
        (PermissionDeniedError("Insufficient repository permission"), 403, {}),
        (InsufficientTokenScopeError(), 403, {}),
        (RepositoryNotFoundError(), 404, {}),
        (TokenNotFoundError(), 404, {}),
        (ConflictError("An organization must retain an administrator"), 409, {}),
        (TokenRevokedError(), 409, {}),
        (PayloadTooLargeError("File is too large"), 413, {}),
        (UnprocessableInputError("File is not in this comparison"), 422, {}),
        (RateLimitError(retry_after=17), 429, {"retry-after": "17"}),
        (TokenAuthenticationLimitError(), 429, {"retry-after": "60"}),
        (ServiceUnavailableError(), 503, {}),
        (TokenIssuanceError(), 503, {}),
    ],
)
def test_application_error_contract(error: ApplicationError, code: int, headers: dict[str, str]) -> None:
    def fail() -> None:
        raise error

    app.dependency_overrides[get_repository_store] = fail
    try:
        with TestClient(app) as client:
            response = client.get(f"{settings.API_V1_STR}/repositories/")
    finally:
        app.dependency_overrides.pop(get_repository_store, None)
    assert response.status_code == code
    assert response.json() == {"detail": error.detail}
    for name in ("www-authenticate", "retry-after"):
        assert response.headers.get(name) == headers.get(name)
