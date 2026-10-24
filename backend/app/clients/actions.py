"""Workflow persistence with database locks for concurrent event handlers."""

from __future__ import annotations

from contextlib import AbstractAsyncContextManager, asynccontextmanager
from typing import TYPE_CHECKING, Protocol

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.clients.database import SQLStore
from app.entities.actions import WorkflowRun

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncSession


class ActionsStore(Protocol):
    """Storage contract for on-demand workflow orchestration."""

    async def add_run(self, run: WorkflowRun) -> WorkflowRun:
        """Insert a run, deduplicating delivery of the same event."""
        ...

    async def list_runs(self, repo_id: UUID, limit: int = 100) -> list[WorkflowRun]:
        """List recent repository runs."""
        ...

    async def runs_for_commit(self, repo_id: UUID, sha: str) -> list[WorkflowRun]:
        """List runs for the exact PR head, newest first."""
        ...

    async def active_runs(self, repo_id: UUID | None = None) -> list[tuple[UUID, UUID]]:
        """List runs needing collection, paired with their repository."""
        ...

    def locked(self, repo_id: UUID, run_id: UUID) -> AbstractAsyncContextManager[WorkflowRun | None]:
        """Lock a run for mutation; concurrent event handlers skip it."""
        ...


class SQLActionsStore(SQLStore[WorkflowRun]):
    """Persist run updates atomically under a PostgreSQL row lock."""

    def __init__(self, db: AsyncSession) -> None:
        """Use the request-scoped database session."""
        super().__init__(db, WorkflowRun)

    async def add_run(self, run: WorkflowRun) -> WorkflowRun:
        """Insert once per repository, workflow, and event delivery."""
        values = {
            column.name: getattr(run, column.name)
            for column in WorkflowRun.__table__.columns
            if getattr(run, column.name) is not None
        }
        await self.db.execute(insert(WorkflowRun).values(**values).on_conflict_do_nothing())
        await self.db.commit()
        result = await self.db.scalar(
            select(WorkflowRun).where(
                WorkflowRun.repo_id == run.repo_id,
                WorkflowRun.workflow == run.workflow,
                WorkflowRun.event_key == run.event_key,
            )
        )
        if result is None:
            raise RuntimeError("Workflow insertion did not return a run")
        return result

    async def list_runs(self, repo_id: UUID, limit: int = 100) -> list[WorkflowRun]:
        """Read recent runs without provider side effects."""
        return list(
            await self.db.scalars(
                select(WorkflowRun)
                .where(WorkflowRun.repo_id == repo_id)
                .order_by(WorkflowRun.created_at.desc())
                .limit(limit)
            )
        )

    async def runs_for_commit(self, repo_id: UUID, sha: str) -> list[WorkflowRun]:
        """Select commit checks without truncating to the recent history page."""
        return list(
            await self.db.scalars(
                select(WorkflowRun)
                .where(WorkflowRun.repo_id == repo_id, WorkflowRun.sha == sha)
                .order_by(WorkflowRun.created_at.desc())
            )
        )

    async def active_runs(self, repo_id: UUID | None = None) -> list[tuple[UUID, UUID]]:
        """List active runs for repository cancellation."""
        query = select(WorkflowRun.repo_id, WorkflowRun.id).where(WorkflowRun.status.in_(["queued", "running"]))
        query = query.where(WorkflowRun.repo_id == repo_id) if repo_id is not None else query.limit(50)
        rows = await self.db.execute(query.order_by(WorkflowRun.updated_at))
        return [(row.repo_id, row.id) for row in rows]

    @asynccontextmanager
    async def locked(self, repo_id: UUID, run_id: UUID) -> AsyncGenerator[WorkflowRun | None]:
        """Commit the complete state transition, releasing the lock on failure."""
        try:
            run = await self.db.scalar(
                select(WorkflowRun)
                .where(WorkflowRun.repo_id == repo_id, WorkflowRun.id == run_id)
                .with_for_update(skip_locked=True)
                .execution_options(populate_existing=True)
            )
            yield run
            await self.db.commit()
        except BaseException:
            await self.db.rollback()
            raise
