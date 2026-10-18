"""Engine-independent Git packs in object storage, with refs and a catalog in Redis.

The catalog is authoritative metadata, not an eventually consistent response cache.
It is updated after complete pack/index uploads and before publishing refs. Existing
repositories bootstrap it with one listing; ordinary reads never list blobs again.
"""

from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING

from fastapi.concurrency import run_in_threadpool

from app.types import MergeResult

if TYPE_CHECKING:
    import uuid

    from app.clients.blob_storage import BlobStorageClient
    from app.clients.redis import AbstractRedisClient
    from app.types import RepositoryChanges

PACK_PREFIX = "packs/"
REF_PREFIX = "refs/"
CATALOG = "pack-catalog:v1"


def normalize_path(path: str) -> str:
    """Return a repository storage prefix with a .git suffix."""
    path = path.strip("/")
    return path if path.endswith(".git") else f"{path}.git"


class GitStore:
    """Persist standard Git pack/index pairs independently of the Git engine."""

    def __init__(self, blob: BlobStorageClient, redis: AbstractRedisClient) -> None:
        """Bind the configured S3/Blob object store and shared Redis metadata."""
        self.blob = blob
        self.redis = redis

    async def _catalog(self, path: str) -> set[str]:
        key = f"{path}/{CATALOG}"
        while True:
            current = await self.redis.get(key)
            if current is not None:
                return set(json.loads(current))
            prefix = f"{path}/{PACK_PREFIX}"
            keys = set(await run_in_threadpool(self.blob.list_keys, prefix))
            packs = {
                name.removeprefix(prefix).removesuffix(".pack")
                for name in keys
                if name.endswith(".pack") and name.removesuffix(".pack") + ".idx" in keys
            }
            if await self.redis.compare_and_set({key: None}, {key: json.dumps(sorted(packs))}):
                return packs

    async def _update_catalog(self, path: str, additions: set[str], deletions: set[str]) -> None:
        key = f"{path}/{CATALOG}"
        while True:
            current = await self.redis.get(key)
            if current is None:
                await self._catalog(path)
                continue
            names = (set(json.loads(current)) | additions) - deletions
            if await self.redis.compare_and_set({key: current.decode()}, {key: json.dumps(sorted(names))}):
                return

    async def load(self, repo_path: str) -> tuple[set[str], dict[str, bytes]]:
        """Read live refs before the pack catalog without downloading objects."""
        path = normalize_path(repo_path)
        refs: dict[str, bytes] = {}
        prefix = f"{path}/{REF_PREFIX}"
        keys = await self.redis.scan_keys(f"{prefix}*")
        for start in range(0, len(keys), 16):
            batch = keys[start : start + 16]
            values = await asyncio.gather(*(self.redis.get(key) for key in batch))
            refs.update({key.removeprefix(prefix): value for key, value in zip(batch, values, strict=True) if value})
        return await self._catalog(path), refs

    async def save(self, repo_path: str, changes: RepositoryChanges) -> None:
        """Publish already uploaded pack pairs in the catalog before writing refs."""
        path = normalize_path(repo_path)
        additions = changes.get("pack_additions", set())
        deletions = changes.get("pack_deletes", set())
        if additions or deletions:
            await self._update_catalog(path, additions, deletions)
            for name in deletions:
                await run_in_threadpool(self.blob.delete, f"{path}/{PACK_PREFIX}{name}.pack")
                await run_in_threadpool(self.blob.delete, f"{path}/{PACK_PREFIX}{name}.idx")
        prefix = f"{path}/{REF_PREFIX}"
        for name, value in changes.get("ref_puts", {}).items():
            await self.redis.set(f"{prefix}{name.decode()}", value)
        for name in changes.get("ref_deletes", set()):
            await self.redis.delete(f"{prefix}{name.decode()}")

    async def copy(self, source: str, destination: str) -> None:
        """Copy known pack pairs and all ref/checkpoint metadata without listing blobs."""
        source, destination = normalize_path(source), normalize_path(destination)
        # Initialize before uploads so concurrent catalog updates cannot be overwritten.
        existing = await self._catalog(destination)
        names = await self._catalog(source)

        def copy_packs() -> None:
            for name in sorted(names - existing):
                for suffix in ("pack", "idx"):
                    with self.blob.open(f"{source}/{PACK_PREFIX}{name}.{suffix}") as stream:
                        self.blob.put(f"{destination}/{PACK_PREFIX}{name}.{suffix}", stream)

        await run_in_threadpool(copy_packs)
        await self._update_catalog(destination, names, set())
        for key in await self.redis.scan_keys(f"{source}/*"):
            if key == f"{source}/{CATALOG}":
                continue
            value = await self.redis.get(key)
            if value is not None:
                await self.redis.set(destination + key[len(source) :], value)

    async def delete(self, repo_path: str) -> None:
        """Delete all blobs, including incomplete uploads, and all repository metadata."""
        path = normalize_path(repo_path)
        # Deletion deliberately lists: a failed upload may not be in the catalog.
        for key in await run_in_threadpool(self.blob.list_keys, f"{path}/"):
            await run_in_threadpool(self.blob.delete, key)
        for key in await self.redis.scan_keys(f"{path}/*"):
            await self.redis.delete(key)

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

    async def compare_and_set(
        self, repo_path: str, expected: dict[str, str | None], updates: dict[str, str | None]
    ) -> bool:
        """Atomically apply relative metadata updates while expected values still match."""
        prefix = f"{normalize_path(repo_path)}/"
        return await self.redis.compare_and_set(
            {prefix + key: value for key, value in expected.items()},
            {prefix + key: value for key, value in updates.items()},
        )
