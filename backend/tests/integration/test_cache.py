"""End-to-end tests for CDN cache headers and cache invalidation."""

from __future__ import annotations

import httpx2

from tests.integration.conftest import create_repository_row
from tests.integration.test_social_features import _push_repo

REF_CACHE_CONTROL = "public, max-age=0, s-maxage=60, stale-while-revalidate=300"
IMMUTABLE_CACHE_CONTROL = "public, max-age=31536000, immutable"
PRIVATE_CACHE_CONTROL = "private, no-store"


def test_ref_content_is_cached_with_short_ttl(app_url: str) -> None:
    _push_repo(app_url, "admin/cacherepo.git")

    response = httpx2.get(f"{app_url}/api/v1/repositories/admin/cacherepo/branches")

    assert response.headers["cache-control"] == REF_CACHE_CONTROL


def test_commit_content_is_immutable(app_url: str) -> None:
    _push_repo(app_url, "admin/cacherepo.git")

    commits = httpx2.get(f"{app_url}/api/v1/repositories/admin/cacherepo/commits").json()
    sha = commits["data"][0]["sha"]

    response = httpx2.get(f"{app_url}/api/v1/repositories/admin/cacherepo/commits/{sha}")

    assert response.headers["cache-control"] == IMMUTABLE_CACHE_CONTROL


def test_private_repository_is_not_cached(app_url: str) -> None:
    create_repository_row("admin", "privaterepo", is_private=True)

    response = httpx2.get(f"{app_url}/api/v1/repositories/admin/privaterepo/branches")

    assert response.headers["cache-control"] == PRIVATE_CACHE_CONTROL


def test_push_invalidates_cached_reads(app_url: str) -> None:
    _push_repo(app_url, "admin/invalid.git")
    first = httpx2.get(f"{app_url}/api/v1/repositories/admin/invalid/tags").json()
    assert first["count"] == 0

    _push_repo(app_url, "admin/invalid.git", tag="v1.0.0")
    second = httpx2.get(f"{app_url}/api/v1/repositories/admin/invalid/tags").json()

    assert second["count"] == 1
