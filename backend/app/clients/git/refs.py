"""Typed storage operations for Git branch tips and retained PR revisions."""

import asyncio
import json
from dataclasses import asdict
from typing import TYPE_CHECKING

from app.clients.git.storage import REF_PREFIX
from app.clients.git.types import MergeResult

if TYPE_CHECKING:
    import uuid

    from app.clients.redis import AbstractRedisClient


class GitRefStore:
    """Keep Redis keys and merge persistence out of repository services."""

    def __init__(self, redis: AbstractRedisClient) -> None:
        """Bind the configured Redis adapter."""
        self.redis = redis

    @staticmethod
    def _ref(owner: str, name: str, ref: str) -> str:
        return f"{owner}/{name}.git/{REF_PREFIX}{ref}"

    @staticmethod
    def _checkpoint(owner: str, name: str, pull_id: uuid.UUID) -> str:
        return f"{owner}/{name}.git/merge-state/{pull_id}"

    async def branch_heads(self, owner: str, name: str, base: str, head: str) -> tuple[str | None, str | None]:
        """Read live branch tips without loading Git objects."""
        before, after = await asyncio.gather(
            self.redis.get(self._ref(owner, name, f"refs/heads/{base}")),
            self.redis.get(self._ref(owner, name, f"refs/heads/{head}")),
        )
        return before.decode() if before else None, after.decode() if after else None

    async def completed_merge(self, owner: str, name: str, pull_id: uuid.UUID) -> MergeResult | None:
        """Read the durable result of a previously published merge."""
        checkpoint = await self.redis.get(self._checkpoint(owner, name, pull_id))
        return MergeResult(**json.loads(checkpoint)) if checkpoint else None

    async def publish_merge(
        self,
        owner: str,
        name: str,
        number: int,
        base_branch: str,
        head_branch: str,
        result: MergeResult,
        delete_branch: bool,
        *,
        pull_id: uuid.UUID,
    ) -> bool:
        """Publish retained revisions only while both branch tips and checkpoint still match."""
        base = self._ref(owner, name, f"refs/heads/{base_branch}")
        head = self._ref(owner, name, f"refs/heads/{head_branch}")
        checkpoint = self._checkpoint(owner, name, pull_id)
        updates: dict[str, str | None] = {
            base: result.commit,
            self._ref(owner, name, f"refs/pull/{number}/base"): result.base,
            self._ref(owner, name, f"refs/pull/{number}/head"): result.head,
            self._ref(owner, name, f"refs/pull/{number}/merge"): result.commit,
            checkpoint: json.dumps(asdict(result)),
        }
        if delete_branch:
            updates[head] = None
        return await self.redis.compare_and_set({base: result.base, head: result.head, checkpoint: None}, updates)
