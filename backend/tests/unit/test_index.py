"""Tests for the application setup and global exception handler."""

from __future__ import annotations

import logging
import sys
from typing import TYPE_CHECKING

from fastapi.testclient import TestClient

from app.api.dependencies import get_repository_store
from app.config import settings
from app.index import app

if TYPE_CHECKING:
    import pytest


def test_global_exception_handler_logs_traceback(capsys: pytest.CaptureFixture[str]) -> None:
    """Unhandled exceptions return 500 and are logged with a stack trace."""

    def _raise() -> None:
        raise RuntimeError("boom")

    logger = logging.getLogger("app")
    handler = logging.StreamHandler(sys.stderr)
    logger.addHandler(handler)
    app.dependency_overrides[get_repository_store] = _raise
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.get(f"{settings.API_V1_STR}/repositories/")
    finally:
        logger.removeHandler(handler)
        app.dependency_overrides.pop(get_repository_store, None)

    assert response.status_code == 500
    captured = capsys.readouterr()
    assert "Unhandled exception - GET " in captured.err
    assert "Traceback (most recent call last)" in captured.err
    assert "RuntimeError: boom" in captured.err
