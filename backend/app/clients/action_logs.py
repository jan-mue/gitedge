"""PostgreSQL log indexes; payloads live in Blob/S3."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, override

from sqlalchemy import select

from app.clients.database import SQLStore
from app.entities.actions import WorkflowAttempt, WorkflowLogChunk, WorkflowRun

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True)
class LogContext:
    """Committed cursor and state for an authorized attempt."""

    attempt_id: uuid.UUID
    job_id: str
    log_seq: int
    status: str


class ActionsLogStore(ABC):
    """Log index contract shared by SQL and fake clients."""

    @abstractmethod
    async def context(self, repo_id: uuid.UUID, run_id: uuid.UUID, attempt_id: uuid.UUID) -> LogContext | None:
        """Read attempt metadata within its repository and release the transaction."""

    @abstractmethod
    async def chunks(self, attempt_id: uuid.UUID, after: int) -> list[WorkflowLogChunk]:
        """Read a bounded page of indexes and release the transaction."""

    @abstractmethod
    async def chunk(self, chunk_id: uuid.UUID) -> WorkflowLogChunk | None:
        """Check an upload retry inside the run transaction."""

    @abstractmethod
    def stage(self, chunk: WorkflowLogChunk) -> None:
        """Stage an index in the current run transaction."""


class SQLActionsLogStore(ActionsLogStore, SQLStore[WorkflowLogChunk]):
    """Persist chunk indexes in the shared run transaction."""

    def __init__(self, db: AsyncSession) -> None:
        """Use the request session so indexes and cursors commit together."""
        super().__init__(db, WorkflowLogChunk)

    @override
    async def context(self, repo_id: uuid.UUID, run_id: uuid.UUID, attempt_id: uuid.UUID) -> LogContext | None:
        row = (
            await self.db.execute(
                select(WorkflowAttempt.id, WorkflowAttempt.job_id, WorkflowAttempt.log_seq, WorkflowAttempt.status)
                .join(WorkflowRun)
                .where(WorkflowRun.repo_id == repo_id, WorkflowRun.id == run_id, WorkflowAttempt.id == attempt_id)
            )
        ).one_or_none()
        await self.db.commit()
        return LogContext(*row) if row else None

    @override
    async def chunks(self, attempt_id: uuid.UUID, after: int) -> list[WorkflowLogChunk]:
        rows = list(
            await self.db.scalars(
                select(WorkflowLogChunk)
                .where(WorkflowLogChunk.attempt_id == attempt_id, WorkflowLogChunk.to_seq > after)
                .order_by(WorkflowLogChunk.to_seq)
                .limit(2)
            )
        )
        await self.db.commit()
        return rows

    @override
    async def chunk(self, chunk_id: uuid.UUID) -> WorkflowLogChunk | None:
        return await self.db.get(WorkflowLogChunk, chunk_id)

    @override
    def stage(self, chunk: WorkflowLogChunk) -> None:
        self.db.add(chunk)
