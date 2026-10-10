"""Cache-Control policies for repository content served through a CDN."""

from __future__ import annotations

import re

CACHE_CONTROL_IMMUTABLE = "public, max-age=31536000, immutable"
CACHE_CONTROL_REVALIDATE = "public, max-age=0, s-maxage=60, stale-while-revalidate=300"
CACHE_CONTROL_PRIVATE = "private, no-store"
CACHE_CONTROL_NO_STORE = "no-store"

_COMMIT_SHA_RE = re.compile(r"[0-9a-f]{40}")


def is_commit_sha(ref: str) -> bool:
    """Check whether a ref is a full commit SHA.

    Args:
        ref: A Git ref, branch name, or commit SHA.

    Returns:
        True if the ref is a 40-character lowercase hex commit SHA.
    """
    return _COMMIT_SHA_RE.fullmatch(ref) is not None
