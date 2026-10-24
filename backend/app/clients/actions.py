"""Short PostgreSQL transitions and the transactional Actions outbox."""

from __future__ import annotations

import uuid
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Protocol

from sqlalchemy import exists, or_, select, update
from sqlalchemy.dialects.postgresql import insert

from app.clients.database import SQLStore
from app.entities.actions import WorkflowAttempt, WorkflowOutbox, WorkflowRun
from app.exceptions import ActionsUnavailableError
from app.schemas.actions import ActionJob

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Callable

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


class ActionsStore(Protocol):
    """Persist runs, attempt generations, and durable commands."""

    async def add_run(self, run: WorkflowRun, initialize: Callable[[RunState], None] | None = None) -> WorkflowRun:
        """Commit a run and its initial commands together."""
        ...

    async def list_runs(self, repo_id: uuid.UUID, limit: int = 100) -> list[WorkflowRun]:
        """Read repository history."""
        ...

    async def runs_for_commit(self, repo_id: uuid.UUID, sha: str) -> list[WorkflowRun]:
        """Read checks for an immutable commit."""
        ...

    async def active_runs(self, repo_id: uuid.UUID | None = None) -> list[tuple[uuid.UUID, uuid.UUID]]:
        """Find runs with execution or cleanup outstanding."""
        ...

    def transaction(
        self, run_id: uuid.UUID, repo_id: uuid.UUID | None = None
    ) -> AbstractAsyncContextManager[RunState | None]:
        """Serialize a short state transition and commit its outbox."""
        ...

    async def message(self, message_id: uuid.UUID) -> WorkflowOutbox | None:
        """Read a durable command and release the transaction."""
        ...

    async def pending(self, limit: int = 50) -> list[WorkflowOutbox]:
        """Find unpublished or stalled commands."""
        ...

    async def published(self, message_id: uuid.UUID, when: datetime) -> None:
        """Record broker acceptance."""
        ...

    async def current(self, capability: Capability, allow_terminal: bool = False) -> bool:
        """Check whether a capability still owns its job generation."""
        ...

    async def artifacts(self, run_id: uuid.UUID) -> list[str]:
        """Read artifact references from completed attempts."""
        ...


class SQLActionsStore(SQLStore[WorkflowRun]):
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

    async def add_run(self, run: WorkflowRun, initialize: Callable[[RunState], None] | None = None) -> WorkflowRun:
        """Commit a deduplicated run and its initial commands together."""
        try:
            await self.db.execute(insert(WorkflowRun).values(**self._values(run)).on_conflict_do_nothing())
            saved = await self.db.scalar(
                select(WorkflowRun)
                .where(
                    WorkflowRun.repo_id == run.repo_id,
                    WorkflowRun.workflow == run.workflow,
                    WorkflowRun.event_key == run.event_key,
                )
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            if saved is None:
                raise RuntimeError("Workflow insertion did not return a run")
            attempts = list(await self.db.scalars(select(WorkflowAttempt).where(WorkflowAttempt.run_id == saved.id)))
            state = RunState(saved, attempts)
            if initialize:
                initialize(state)
            await self._save(state)
            await self.db.commit()
            return saved
        except BaseException:
            await self.db.rollback()
            raise

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

    async def list_runs(self, repo_id: uuid.UUID, limit: int = 100) -> list[WorkflowRun]:
        """Read persisted repository history."""
        return list(
            await self.db.scalars(
                select(WorkflowRun)
                .where(WorkflowRun.repo_id == repo_id)
                .order_by(WorkflowRun.created_at.desc())
                .limit(limit)
            )
        )

    async def runs_for_commit(self, repo_id: uuid.UUID, sha: str) -> list[WorkflowRun]:
        """Read all checks for an immutable commit."""
        return list(
            await self.db.scalars(
                select(WorkflowRun)
                .where(WorkflowRun.repo_id == repo_id, WorkflowRun.sha == sha)
                .order_by(WorkflowRun.created_at.desc())
            )
        )

    async def active_runs(self, repo_id: uuid.UUID | None = None) -> list[tuple[uuid.UUID, uuid.UUID]]:
        """Find runs with execution or cleanup still outstanding."""
        query = select(WorkflowRun.repo_id, WorkflowRun.id).where(
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
        rows = await self.db.execute(query.order_by(WorkflowRun.updated_at))
        result = [(row.repo_id, row.id) for row in rows]
        await self.db.commit()
        return result

    async def message(self, message_id: uuid.UUID) -> WorkflowOutbox | None:
        """Read a durable command and release the read transaction."""
        result = await self.db.get(WorkflowOutbox, message_id, populate_existing=True)
        await self.db.commit()
        return result

    async def pending(self, limit: int = 50) -> list[WorkflowOutbox]:
        """Find unpublished commands and deliveries needing recovery."""
        now = datetime.now(UTC)
        result = list(
            await self.db.scalars(
                select(WorkflowOutbox)
                .where(
                    WorkflowOutbox.acknowledged_at.is_(None),
                    or_(
                        WorkflowOutbox.published_at.is_(None), WorkflowOutbox.published_at < now - timedelta(seconds=60)
                    ),
                )
                .order_by(WorkflowOutbox.due_at)
                .limit(limit)
            )
        )
        await self.db.commit()
        return result

    async def published(self, message_id: uuid.UUID, when: datetime) -> None:
        """Record broker acceptance separately from command completion."""
        await self.db.execute(update(WorkflowOutbox).where(WorkflowOutbox.id == message_id).values(published_at=when))
        await self.db.commit()

    async def current(self, capability: Capability, allow_terminal: bool = False) -> bool:
        """Check whether this capability still owns its job generation."""
        statuses = ["queued", "starting", "running"] + (["success", "failure", "skipped"] if allow_terminal else [])
        result = await self.db.scalar(
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
        await self.db.commit()
        return result is not None

    async def artifacts(self, run_id: uuid.UUID) -> list[str]:
        """Read artifact references published by completed attempts."""
        result = list(
            await self.db.scalars(
                select(WorkflowAttempt.artifact_key)
                .where(
                    WorkflowAttempt.run_id == run_id,
                    WorkflowAttempt.artifact_key.is_not(None),
                )
                .order_by(WorkflowAttempt.completed_at)
            )
        )
        await self.db.commit()
        return [key for key in result if key is not None]
