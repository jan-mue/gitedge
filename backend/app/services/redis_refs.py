"""Redis-based refs container for Git reference storage.

This module provides a refs container implementation that uses Redis
for storing Git references (branches, tags, HEAD, etc.).
"""

from typing import TYPE_CHECKING, override

from dulwich.objects import ZERO_SHA, ObjectID
from dulwich.refs import SYMREF, Ref, RefsContainer

if TYPE_CHECKING:
    from collections.abc import Callable


class RedisRefsContainer(RefsContainer):
    """RefsContainer implementation using Redis.

    This container stores Git references in Redis. Like R2ObjectStore,
    it's designed to work with pre-loaded data since Redis operations are async
    but dulwich expects synchronous operations.

    Usage:
        1. Create the container
        2. Call load_refs() to pre-fetch refs from Redis
        3. Use the container with dulwich as normal
        4. Call get_pending_changes() to get changes to write back to Redis
    """

    def __init__(
        self,
        logger: Callable[[bytes, bytes, bytes, bytes | None, int | None, int | None, bytes], None] | None = None,
    ) -> None:
        """Initialize RedisRefsContainer.

        Args:
            logger: Optional logger function for reflog entries.
        """
        super().__init__(logger=logger)

        # In-memory refs storage: ref name -> ref value (SHA or SYMREF + target)
        self._refs: dict[Ref, bytes] = {}

        self._peeled: dict[Ref, ObjectID] = {}

        self._pending_puts: dict[Ref, bytes] = {}
        self._pending_deletes: set[Ref] = set()

    def allkeys(self) -> set[Ref]:
        """Return all reference keys.

        Returns:
            Set of all ref names in this container.
        """
        return set(self._refs.keys())

    def read_loose_ref(self, name: Ref) -> bytes | None:
        """Read a loose reference.

        Args:
            name: The ref name to read.

        Returns:
            The ref value (SHA or symref), or None if not found.
        """
        return self._refs.get(name)

    def get_packed_refs(self) -> dict[Ref, ObjectID]:
        """Get packed references.

        Redis-based storage doesn't use packed refs, so this returns empty.

        Returns:
            Empty dictionary.
        """
        return {}

    @override
    def set_symbolic_ref(
        self,
        name: Ref,
        other: Ref,
        committer: bytes | None = None,
        timestamp: int | None = None,
        timezone: int | None = None,
        message: bytes | None = None,
    ) -> None:
        """Make a ref point at another ref (symbolic reference).

        Args:
            name: Name of the ref to set.
            other: Name of the ref to point at.
            committer: Optional committer for reflog.
            timestamp: Optional timestamp for reflog.
            timezone: Optional timezone for reflog.
            message: Optional message for reflog.
        """
        old = self.follow(name)[-1]
        new_value = SYMREF + other
        self._refs[name] = new_value
        self._pending_puts[name] = new_value
        self._pending_deletes.discard(name)

        self._log(
            name,
            old,
            new_value,
            committer=committer,
            timestamp=timestamp,
            timezone=timezone,
            message=message,
        )

    @override
    def set_if_equals(
        self,
        name: Ref,
        old_ref: ObjectID | None,
        new_ref: ObjectID,
        committer: bytes | None = None,
        timestamp: int | None = None,
        timezone: int | None = None,
        message: bytes | None = None,
    ) -> bool:
        """Set a refname to new_ref only if it currently equals old_ref.

        This method can be used for atomic compare-and-swap operations.

        Args:
            name: The refname to set.
            old_ref: The old SHA the refname must refer to, or None to set unconditionally.
            new_ref: The new SHA the refname will refer to.
            committer: Optional committer for reflog.
            timestamp: Optional timestamp for reflog.
            timezone: Optional timezone for reflog.
            message: Optional message for reflog.

        Returns:
            True if the set was successful, False otherwise.
        """
        if old_ref is not None:
            current = self._refs.get(name)
            if current not in (old_ref, ZERO_SHA) and (current is not None or old_ref != ZERO_SHA):
                return False

        self._check_refname(name)
        old = self._refs.get(name)
        self._refs[name] = new_ref
        self._pending_puts[name] = new_ref
        self._pending_deletes.discard(name)

        self._log(
            name,
            old,
            new_ref,
            committer=committer,
            timestamp=timestamp,
            timezone=timezone,
            message=message,
        )
        return True

    @override
    def add_if_new(
        self,
        name: Ref,
        ref: ObjectID,
        committer: bytes | None = None,
        timestamp: int | None = None,
        timezone: int | None = None,
        message: bytes | None = None,
    ) -> bool:
        """Add a new reference only if it does not already exist.

        Args:
            name: Ref name.
            ref: Ref value (SHA).
            committer: Optional committer for reflog.
            timestamp: Optional timestamp for reflog.
            timezone: Optional timezone for reflog.
            message: Optional message for reflog.

        Returns:
            True if the add was successful, False if ref already exists.
        """
        if name in self._refs:
            return False

        self._refs[name] = ref
        self._pending_puts[name] = ref
        self._pending_deletes.discard(name)

        self._log(name, None, ref, committer=committer, timestamp=timestamp, timezone=timezone, message=message)
        return True

    @override
    def remove_if_equals(
        self,
        name: Ref,
        old_ref: ObjectID | None,
        committer: bytes | None = None,
        timestamp: int | None = None,
        timezone: int | None = None,
        message: bytes | None = None,
    ) -> bool:
        """Remove a refname only if it currently equals old_ref.

        Args:
            name: The refname to delete.
            old_ref: The old SHA the refname must refer to, or None to delete unconditionally.
            committer: Optional committer for reflog.
            timestamp: Optional timestamp for reflog.
            timezone: Optional timezone for reflog.
            message: Optional message for reflog.

        Returns:
            True if the delete was successful, False otherwise.
        """
        if old_ref is not None:
            current = self._refs.get(name)
            if current not in (old_ref, ZERO_SHA):
                return False

        try:
            old = self._refs.pop(name)
        except KeyError:
            pass
        else:
            self._pending_deletes.add(name)
            self._pending_puts.pop(name, None)
            self._log(
                name,
                old,
                None,
                committer=committer,
                timestamp=timestamp,
                timezone=timezone,
                message=message,
            )
        return True

    def get_peeled(self, name: Ref) -> ObjectID | None:
        """Return the cached peeled value of a ref, if available.

        Args:
            name: Name of the ref to peel.

        Returns:
            The peeled SHA, or None if not cached.
        """
        return self._peeled.get(name)

    def load_refs_from_data(self, refs: dict[str, bytes]) -> None:
        """Load refs that were pre-fetched from Redis.

        Args:
            refs: Dictionary mapping ref names (as strings) to their values.
        """
        for name, value in refs.items():
            self._refs[Ref(name.encode() if isinstance(name, str) else name)] = value

    def get_pending_puts(self) -> dict[Ref, bytes]:
        """Get pending ref updates.

        Returns:
            Dictionary mapping ref names to new values.
        """
        return dict(self._pending_puts)

    def get_pending_deletes(self) -> set[Ref]:
        """Get pending ref deletions.

        Returns:
            Set of ref names to delete.
        """
        return set(self._pending_deletes)

    def clear_pending(self) -> None:
        """Clear all pending changes.

        Call this after successfully flushing changes to Redis.
        """
        self._pending_puts.clear()
        self._pending_deletes.clear()

    def add_packed_refs(self, new_refs: dict[Ref, ObjectID | None]) -> None:  # type: ignore[override]
        """Add packed refs (no-op for Redis-based storage).

        Args:
            new_refs: Refs to add.
        """
        # Redis doesn't distinguish between packed and loose refs
        for name, value in new_refs.items():
            if value is None:
                self.remove_if_equals(name, None)
            else:
                self.set_if_equals(name, None, value)

    def pack_refs(self, all_refs: bool = False) -> None:
        """Pack loose refs (no-op for Redis-based storage).

        Args:
            all_refs: If True, pack all refs. If False, only pack tags.
        """
        # Redis doesn't need packing
