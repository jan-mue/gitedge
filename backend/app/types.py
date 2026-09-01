"""Type definitions for the application."""

from __future__ import annotations

from typing import TYPE_CHECKING, TypedDict

if TYPE_CHECKING:
    from dulwich.refs import Ref


class RepositoryChanges(TypedDict, total=False):
    """Type definition for repository pending changes.

    Attributes:
        pack_uploads: Dict mapping pack basenames to (pack_data, index_data) tuples.
        pack_deletes: Set of pack basenames to delete.
        ref_puts: Dict mapping ref names (Ref type from dulwich) to new values.
        ref_deletes: Set of ref names (Ref type from dulwich) to delete.
    """

    pack_uploads: dict[str, tuple[bytes, bytes]]
    pack_deletes: set[str]
    ref_puts: dict[Ref, bytes]
    ref_deletes: set[Ref]
