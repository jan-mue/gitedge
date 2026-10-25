"""Short PostgreSQL transitions and the transactional Actions outbox."""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, override

from sqlalchemy import exists, or_, select, update
from sqlalchemy.dialects.postgresql import insert

from app.clients.database import SQLStore
from app.entities.actions import WorkflowAttempt, WorkflowOutbox, WorkflowRun
from app.exceptions import ActionsUnavailableError
from app.schemas.actions import ActionJob

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Callable

    from sqlalchemy import Select
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.schemas.action_dispatch import Capability, DeliveryKind


@dataclass
class RunState:
    """Mutable state held only during a short database transition."""

    run: WorkflowRun
    attempts: list[WorkflowAttempt]
    jobs: list[ActionJob] = field(init=False)
    messages: list[WorkflowOutbox] = field(default_factory=list)
    acknowledged: list[uuid.UUID] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Decode the persisted public job snapshot."""
        self.jobs = [ActionJob.model_validate(job) for job in self.run.jobs]

    def job(self, attempt: WorkflowAttempt) -> ActionJob | None:
        """Find the job still owned by this attempt."""
        return next((job for job in self.jobs if job.id == attempt.job_id and job.attempt_id == attempt.id), None)

    def attempt(self, attempt_id: uuid.UUID) -> WorkflowAttempt | None:
        """Find an execution generation within this run."""
        return next((attempt for attempt in self.attempts if attempt.id == attempt_id), None)

    def enqueue(self, kind: DeliveryKind, attempt: WorkflowAttempt, delay: float = 0, key: str = "") -> None:
        """Append an idempotent command to the current transaction."""
        self.messages.append(
            WorkflowOutbox(
                id=uuid.uuid5(attempt.id, f"{kind}:{key}"),
                run_id=self.run.id,
                attempt_id=attempt.id,
                kind=kind,
                due_at=datetime.now(UTC) + timedelta(seconds=delay),
            )
        )


class ActionsStore(ABC):
    """Contract shared by PostgreSQL and in-memory Actions stores."""

    @abstractmethod
    async def add_run(self, run: WorkflowRun, initialize: Callable[[RunState], None] | None = None) -> WorkflowRun:
        """Commit a run and its initial outbox commands atomically."""

    @abstractmethod
    async def list_runs(
        self, repo_id: uuid.UUID, limit: int | None = 100, *, sha: str | None = None
    ) -> list[WorkflowRun]:
        """Read repository history or checks for a commit."""

    @abstractmethod
    async def active_runs(self, repo_id: uuid.UUID | None = None) -> list[uuid.UUID]:
        """Find runs with execution or cleanup outstanding."""

    @abstractmethod
    def transaction(
        self, run_id: uuid.UUID, repo_id: uuid.UUID | None = None
    ) -> AbstractAsyncContextManager[RunState | None]:
        """Serialize and commit a short state transition."""

    @abstractmethod
    async def message(self, message_id: uuid.UUID) -> WorkflowOutbox | None:
        """Read a durable command."""

    @abstractmethod
    async def pending(self, limit: int = 50) -> list[WorkflowOutbox]:
        """Find commands needing publication or recovery."""

    @abstractmethod
    async def published(self, message_id: uuid.UUID, when: datetime) -> None:
        """Record broker acceptance."""

    @abstractmethod
    async def current(self, capability: Capability, allow_terminal: bool = False) -> bool:
        """Check ownership of the current attempt generation."""

    @abstractmethod
    async def artifacts(self, run_id: uuid.UUID) -> list[str]:
        """Read artifact references from completed attempts."""


class SQLActionsStore(ActionsStore, SQLStore[WorkflowRun]):
    """Commit state transitions before any provider or queue I/O."""

    def __init__(self, db: AsyncSession) -> None:
        """Share the request's session for short atomic run transitions."""
        super().__init__(db, WorkflowRun)

    @staticmethod
    def _values(entity: WorkflowRun | WorkflowOutbox) -> dict[str, object]:
        return {
            column.name: value
            for column in entity.__table__.columns
            if (value := getattr(entity, column.name)) is not None
        }

    async def _save(self, state: RunState) -> None:
        state.run.jobs = [job.model_dump(mode="json") for job in state.jobs]
        state.run.updated_at = datetime.now(UTC)
        self.db.add_all(state.attempts)
        await self.db.flush()
        if state.messages:
            await self.db.execute(
                insert(WorkflowOutbox)
                .values([self._values(message) for message in state.messages])
                .on_conflict_do_nothing()
            )
        if state.acknowledged:
            await self.db.execute(
                update(WorkflowOutbox)
                .where(WorkflowOutbox.id.in_(state.acknowledged))
                .values(acknowledged_at=datetime.now(UTC))
            )

    @override
    async def add_run(self, run: WorkflowRun, initialize: Callable[[RunState], None] | None = None) -> WorkflowRun:
        """Insert a run and initialize it through the normal atomic transition."""
        await self.db.execute(insert(WorkflowRun).values(**self._values(run)).on_conflict_do_nothing())
        run_id = (
            await self.db.scalars(
                select(WorkflowRun.id).where(
                    WorkflowRun.repo_id == run.repo_id,
                    WorkflowRun.workflow == run.workflow,
                    WorkflowRun.event_key == run.event_key,
                )
            )
        ).one()
        async with self.transaction(run_id) as state:
            if state is None:
                raise ActionsUnavailableError("Workflow disappeared during creation")
            if initialize:
                initialize(state)
            return state.run

    @override
    @asynccontextmanager
    async def transaction(self, run_id: uuid.UUID, repo_id: uuid.UUID | None = None) -> AsyncGenerator[RunState | None]:
        """Serialize a short state transition and commit its outbox."""
        try:
            query = select(WorkflowRun).where(WorkflowRun.id == run_id)
            if repo_id is not None:
                query = query.where(WorkflowRun.repo_id == repo_id)
            run = await self.db.scalar(
                query.with_for_update(skip_locked=True).execution_options(populate_existing=True)
            )
            if run is None:
                if await self.db.scalar(query.with_only_columns(WorkflowRun.id)):
                    raise ActionsUnavailableError("Workflow transition is busy")
                yield None
            else:
                attempts = list(
                    await self.db.scalars(
                        select(WorkflowAttempt)
                        .where(WorkflowAttempt.run_id == run_id)
                        .execution_options(populate_existing=True)
                    )
                )
                state = RunState(run, attempts)
                yield state
                await self._save(state)
            await self.db.commit()
        except BaseException:
            await self.db.rollback()
            raise

    async def _read[T](self, query: Select[T]) -> list[T]:
        result = list(await self.db.scalars(query))
        await self.db.commit()
        return result

    @override
    async def list_runs(
        self, repo_id: uuid.UUID, limit: int | None = 100, *, sha: str | None = None
    ) -> list[WorkflowRun]:
        """Read persisted history without retaining a database transaction."""
        query = select(WorkflowRun).where(WorkflowRun.repo_id == repo_id).order_by(WorkflowRun.created_at.desc())
        if sha is not None:
            query = query.where(WorkflowRun.sha == sha)
        return await self._read(query.limit(limit))

    @override
    async def active_runs(self, repo_id: uuid.UUID | None = None) -> list[uuid.UUID]:
        """Find runs with execution or cleanup still outstanding."""
        query = select(WorkflowRun.id).where(
            or_(
                WorkflowRun.status.in_(["queued", "running"]),
                exists(
                    select(WorkflowOutbox.id).where(
                        WorkflowOutbox.run_id == WorkflowRun.id,
                        WorkflowOutbox.kind == "cleanup",
                        WorkflowOutbox.acknowledged_at.is_(None),
                    )
                ),
            )
        )
        query = query.where(WorkflowRun.repo_id == repo_id) if repo_id else query.limit(50)
        return await self._read(query.order_by(WorkflowRun.updated_at))

    @override
    async def message(self, message_id: uuid.UUID) -> WorkflowOutbox | None:
        """Read a durable command and release the read transaction."""
        result = await self.db.get(WorkflowOutbox, message_id, populate_existing=True)
        await self.db.commit()
        return result

    @override
    async def pending(self, limit: int = 50) -> list[WorkflowOutbox]:
        """Find unpublished commands and deliveries needing recovery."""
        now = datetime.now(UTC)
        return await self._read(
            select(WorkflowOutbox)
            .where(
                WorkflowOutbox.acknowledged_at.is_(None),
                or_(WorkflowOutbox.published_at.is_(None), WorkflowOutbox.published_at < now - timedelta(seconds=60)),
            )
            .order_by(WorkflowOutbox.due_at)
            .limit(limit)
        )

    @override
    async def published(self, message_id: uuid.UUID, when: datetime) -> None:
        """Record broker acceptance separately from command completion."""
        await self.db.execute(update(WorkflowOutbox).where(WorkflowOutbox.id == message_id).values(published_at=when))
        await self.db.commit()

    @override
    async def current(self, capability: Capability, allow_terminal: bool = False) -> bool:
        """Check whether this capability still owns its job generation."""
        statuses = ["queued", "starting", "running"] + (["success", "failure", "skipped"] if allow_terminal else [])
        return bool(
            await self._read(
                select(WorkflowAttempt.id)
                .join(WorkflowRun)
                .where(
                    WorkflowAttempt.id == capability.id,
                    WorkflowAttempt.fence == capability.fence,
                    WorkflowAttempt.generation == capability.generation,
                    WorkflowAttempt.job_id == capability.job_id,
                    WorkflowAttempt.status.in_(statuses),
                    WorkflowRun.id == capability.run,
                    WorkflowRun.repo_id == capability.repo,
                    WorkflowRun.status != "cancelled",
                    WorkflowRun.jobs.contains([{"id": capability.job_id, "attempt_id": str(capability.id)}]),
                )
            )
        )

    @override
    async def artifacts(self, run_id: uuid.UUID) -> list[str]:
        """Read artifact references published by completed attempts."""
        result = await self._read(
            select(WorkflowAttempt.artifact_key)
            .where(
                WorkflowAttempt.run_id == run_id,
                WorkflowAttempt.artifact_key.is_not(None),
            )
            .order_by(WorkflowAttempt.completed_at)
        )
        return [key for key in result if key is not None]
