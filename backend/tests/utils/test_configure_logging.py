from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.dependencies import check_database_connection
from app.utils.configure_logging import configure_logging

if TYPE_CHECKING:
    from pytest import CaptureFixture
    from pytest_mock import MockerFixture


def test_unhandled_exception_is_logged(app: FastAPI, mocker: MockerFixture, capsys: CaptureFixture[str]) -> None:
    """Unhandled exceptions return 500 and are logged via loguru."""
    mock_settings = mocker.patch("app.utils.configure_logging.settings")
    mock_settings.LOG_LEVEL.value = "DEBUG"
    client = TestClient(app, raise_server_exceptions=False)

    # Call configure_logging() again to use capsys stdout
    configure_logging()

    def _failing_check() -> bool:
        raise RuntimeError("deliberate failure")

    app.dependency_overrides[check_database_connection] = _failing_check

    response = client.get("/api/v1/utils/health-check/")

    assert response.status_code == 500
    assert response.json() == {"detail": "Internal server error"}
    captured = capsys.readouterr()
    assert "Unhandled exception" in captured.out
    assert "deliberate failure" in captured.out
    assert "/api/v1/utils/health-check" in captured.out
