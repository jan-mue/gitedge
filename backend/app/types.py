"""Type definitions for the application."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, TypedDict

if TYPE_CHECKING:
    import uuid

    from app.schemas.repositories import MergeMessage, MergeMethod


class RepositoryChanges(TypedDict, total=False):
    """Type definition for repository pending changes.

    Attributes:
        pack_additions: Set of newly uploaded pack basenames.
        pack_deletes: Set of pack basenames to delete.
        ref_puts: Dict mapping ref names as UTF-8 bytes to new values.
        ref_deletes: Set of ref names as UTF-8 bytes to delete.
    """

    pack_additions: set[str]
    pack_deletes: set[str]
    ref_puts: dict[bytes, bytes]
    ref_deletes: set[bytes]


@dataclass(frozen=True)
class GitHttpRequest:
    """Decoded HTTP input for a Git engine's smart/dumb HTTP implementation."""

    method: str
    path: str
    query: str
    headers: dict[str, str]
    body: bytes
    scheme: str = "http"
    hostname: str = "localhost"
    port: int = 80


@dataclass(frozen=True)
class GitHttpResponse:
    """Buffered Git protocol output, independent of the web framework."""

    body: bytes
    status: int
    headers: dict[str, str]


@dataclass(frozen=True)
class MergeResult:
    """Immutable revisions retained for publication and recovery."""

    base: str
    head: str
    commit: str


@dataclass(frozen=True)
class MergeRequest:
    """Validated merge policy and user input passed to a Git engine."""

    owner: str
    name: str
    number: int
    pull_id: uuid.UUID
    base_branch: str
    head_branch: str
    method: MergeMethod
    template: MergeMessage
    title: str
    body: str | None
    identity: bytes
    delete_branch: bool
    expected_base: str | None = None
    expected_head: str | None = None
