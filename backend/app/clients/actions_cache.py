"""Searchable cache metadata and atomic publication of payload generations."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.clients.database import SQLStore
from app.entities.actions import WorkflowCacheEntry

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncSession


class ActionsCacheStore(SQLStore[WorkflowCacheEntry]):
    """Keep prefix lookup out of cache providers that cannot enumerate keys."""

    def __init__(self, db: AsyncSession) -> None:
        """Use the request-scoped session."""
        super().__init__(db, WorkflowCacheEntry)

    async def candidates(self, repo_id: UUID, prefix: str, version: str) -> list[WorkflowCacheEntry]:
        """Select escaped prefixes, bounded to 128 candidates per restore key."""
        return list(
            await self.db.scalars(
                select(WorkflowCacheEntry)
                .where(
                    WorkflowCacheEntry.repo_id == repo_id,
                    WorkflowCacheEntry.version == version,
                    WorkflowCacheEntry.key.startswith(prefix, autoescape=True),
                )
                .order_by((WorkflowCacheEntry.key == prefix).desc(), WorkflowCacheEntry.updated_at.desc())
                .limit(128)
            )
        )

    async def payload(self, repo_id: UUID, payload_id: UUID) -> WorkflowCacheEntry | None:
        """Never return expired metadata or another repository's entry."""
        return await self.db.scalar(
            select(WorkflowCacheEntry).where(
                WorkflowCacheEntry.repo_id == repo_id,
                WorkflowCacheEntry.payload_id == payload_id,
                WorkflowCacheEntry.expires_at > datetime.now(UTC),
            )
        )

    async def publish(self, entry: WorkflowCacheEntry, previous: UUID | None) -> WorkflowCacheEntry:
        """Replace only the missing or expired generation observed before uploading."""
        statement = insert(WorkflowCacheEntry).values(
            repo_id=entry.repo_id,
            key=entry.key,
            version=entry.version,
            payload_id=entry.payload_id,
            size=entry.size,
            checksum=entry.checksum,
            expires_at=entry.expires_at,
        )
        statement = statement.on_conflict_do_update(
            index_elements=[WorkflowCacheEntry.repo_id, WorkflowCacheEntry.key, WorkflowCacheEntry.version],
            set_={
                "payload_id": entry.payload_id,
                "size": entry.size,
                "checksum": entry.checksum,
                "expires_at": entry.expires_at,
                "updated_at": datetime.now(UTC),
            },
            where=WorkflowCacheEntry.payload_id == previous
            if previous
            else WorkflowCacheEntry.expires_at <= datetime.now(UTC),
        )
        await self.db.execute(statement)
        await self.db.commit()
        result = await self.db.scalar(
            select(WorkflowCacheEntry)
            .where(
                WorkflowCacheEntry.repo_id == entry.repo_id,
                WorkflowCacheEntry.key == entry.key,
                WorkflowCacheEntry.version == entry.version,
            )
            .execution_options(populate_existing=True)
        )
        if result is None:
            raise RuntimeError("Cache publication did not return metadata")
        return result
