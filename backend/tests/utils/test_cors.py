from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from app.config import DEV_FRONTEND_ORIGINS, settings

if TYPE_CHECKING:
    from fastapi.testclient import TestClient
    from pytest import MonkeyPatch

PRODUCTION_ORIGIN = "https://gitedge-app.vercel.app"


def test_production_returns_only_production_frontend_origin(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "VERCEL_ENV", "production")
    monkeypatch.setattr(settings, "FRONTEND_HOST", PRODUCTION_ORIGIN)
    monkeypatch.setattr(
        settings,
        "VERCEL_RELATED_PROJECTS",
        json.dumps([{"preview": {"branch": "gitedge-frontend-git-feature.vercel.sh"}}]),
    )
    assert settings.cors_origins == [PRODUCTION_ORIGIN]


def test_preview_extracts_branch_and_custom_environment(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "VERCEL_ENV", "preview")
    monkeypatch.setattr(
        settings,
        "VERCEL_RELATED_PROJECTS",
        json.dumps(
            [
                {
                    "project": {"id": "prj_frontend", "name": "gitedge-frontend"},
                    "preview": {
                        "branch": "gitedge-frontend-git-main.vercel.sh",
                        "customEnvironment": "gitedge-frontend-git-staging.vercel.sh",
                    },
                }
            ]
        ),
    )
    assert settings.cors_origins == [
        "https://gitedge-frontend-git-staging.vercel.sh",
        "https://gitedge-frontend-git-main.vercel.sh",
    ]


@pytest.mark.parametrize(
    "raw",
    [
        None,
        "",
        "not-json{",
        "[]",
        '{"not": "a list"}',
        "[1, 2, 3]",
        "[{}]",
        '["no dicts"]',
    ],
)
def test_preview_missing_or_malformed_data_does_not_crash(monkeypatch: MonkeyPatch, raw: str | None) -> None:
    monkeypatch.setattr(settings, "VERCEL_ENV", "preview")
    monkeypatch.setattr(settings, "VERCEL_RELATED_PROJECTS", raw)
    assert settings.cors_origins == []


def test_development_returns_localhost_origins(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "VERCEL_ENV", "development")
    assert settings.cors_origins == list(DEV_FRONTEND_ORIGINS)


def test_origins_are_normalized_and_deduplicated(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "VERCEL_ENV", "preview")
    monkeypatch.setattr(
        settings,
        "VERCEL_RELATED_PROJECTS",
        json.dumps(
            [
                {"preview": {"branch": "gitedge-frontend-git-main.vercel.sh"}},
                {"preview": {"branch": "https://gitedge-frontend-git-main.vercel.sh"}},
                {"preview": {"branch": "gitedge-frontend-git-main.vercel.sh "}},
            ]
        ),
    )
    assert settings.cors_origins == ["https://gitedge-frontend-git-main.vercel.sh"]


@pytest.mark.parametrize(
    "raw",
    [
        "https://",
        "ftp://frontend.example.com",
        "https://frontend.example.com/path",
        "https://frontend.example.com?x=1",
        "https://frontend.example.com#frag",
    ],
)
def test_invalid_origins_are_rejected(monkeypatch: MonkeyPatch, raw: str) -> None:
    monkeypatch.setattr(settings, "VERCEL_ENV", "preview")
    monkeypatch.setattr(
        settings,
        "VERCEL_RELATED_PROJECTS",
        json.dumps([{"preview": {"branch": raw}}]),
    )
    assert settings.cors_origins == []


def test_cors_middleware_echoes_allowed_localhost_origin(client: TestClient) -> None:
    response = client.get(
        "/api/v1/utils/health-check/",
        headers={"Origin": "http://localhost:5173"},
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_cors_middleware_does_not_echo_unknown_origin(client: TestClient) -> None:
    response = client.get(
        "/api/v1/utils/health-check/",
        headers={"Origin": "https://evil.example.com"},
    )
    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers
