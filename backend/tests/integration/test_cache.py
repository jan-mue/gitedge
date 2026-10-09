"""End-to-end tests for CDN cache headers and cache invalidation."""

from __future__ import annotations

import json
import urllib.request

from tests.integration.conftest import create_repository_row
from tests.integration.test_social_features import _push_repo

REF_CACHE_CONTROL = "public, max-age=0, s-maxage=60, stale-while-revalidate=300"
IMMUTABLE_CACHE_CONTROL = "public, max-age=31536000, immutable"
PRIVATE_CACHE_CONTROL = "private, no-store"


def _get(url: str) -> tuple[dict, dict[str, str]]:
    """Fetch a JSON response and its headers.

    Args:
        url: URL to fetch.

    Returns:
        Tuple of (JSON body, lower-cased response headers).
    """
    with urllib.request.urlopen(urllib.request.Request(url)) as response:
        body = json.loads(response.read().decode())
        headers = {name.lower(): value for name, value in response.headers.items()}
    return body, headers


def test_ref_content_is_cached_with_short_ttl(app_url: str) -> None:
    _push_repo(app_url, "admin/cacherepo.git")

    _, headers = _get(f"{app_url}/api/v1/repositories/admin/cacherepo/branches")

    assert headers["cache-control"] == REF_CACHE_CONTROL


def test_commit_content_is_immutable(app_url: str) -> None:
    _push_repo(app_url, "admin/cacherepo.git")

    commits, _ = _get(f"{app_url}/api/v1/repositories/admin/cacherepo/commits")
    sha = commits["data"][0]["sha"]

    _, headers = _get(f"{app_url}/api/v1/repositories/admin/cacherepo/commits/{sha}")

    assert headers["cache-control"] == IMMUTABLE_CACHE_CONTROL


def test_private_repository_is_not_cached(app_url: str) -> None:
    create_repository_row("admin", "privaterepo", is_private=True)

    _, headers = _get(f"{app_url}/api/v1/repositories/admin/privaterepo/branches")

    assert headers["cache-control"] == PRIVATE_CACHE_CONTROL


def test_push_invalidates_cached_reads(app_url: str) -> None:
    _push_repo(app_url, "admin/invalid.git")
    first, _ = _get(f"{app_url}/api/v1/repositories/admin/invalid/commits")
    first_sha = first["data"][0]["sha"]

    _push_repo(app_url, "admin/invalid.git")
    second, _ = _get(f"{app_url}/api/v1/repositories/admin/invalid/commits")

    assert second["data"][0]["sha"] != first_sha
