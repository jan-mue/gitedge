"""In-memory Actions persistence for unit tests."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from contextvars import ContextVar
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, override

from app.clients.actions import ActionsStore, RunState
from app.clients.qstash import ActionsQueue
from app.clients.workflow_compiler import WorkflowCompiler
from app.constants import BACKEND_DIR
from app.exceptions import InvalidDeliveryError
from app.schemas.workflows import CompiledWorkflow

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Callable
    from uuid import UUID

    from pydantic import BaseModel

    from app.entities.actions import WorkflowAttempt, WorkflowOutbox, WorkflowRun
    from app.schemas.action_dispatch import Capability
    from app.schemas.workflows import CompileRequest


class FakeActionsStore(ActionsStore):
    def __init__(self) -> None:

        self.runs: dict[UUID, WorkflowRun] = {}
        self.attempts: dict[UUID, WorkflowAttempt] = {}
        self.messages: dict[UUID, WorkflowOutbox] = {}
        self.locks: dict[UUID, asyncio.Lock] = {}
        self.locked_here = ContextVar("actions_transaction", default=False)
        self.lock_factory = asyncio.Lock

    @property
    def in_transaction(self) -> bool:
        return self.locked_here.get()

    def save(self, state: RunState) -> None:
        state.run.jobs = [job.model_dump(mode="json") for job in state.jobs]
        state.run.updated_at = datetime.now(UTC)
        for attempt in state.attempts:
            self.attempts[attempt.id] = attempt
        for message in state.messages:
            self.messages.setdefault(message.id, message)
        for message_id in state.acknowledged:
            if message_id in self.messages:
                self.messages[message_id].acknowledged_at = datetime.now(UTC)

    @override
    async def add_run(self, run: WorkflowRun, initialize: Callable[[RunState], None] | None = None) -> WorkflowRun:

        existing = next(
            (
                item
                for item in self.runs.values()
                if (item.repo_id, item.workflow, item.event_key) == (run.repo_id, run.workflow, run.event_key)
            ),
            None,
        )
        if existing:
            run = existing
        else:
            run.created_at = run.updated_at = datetime.now(UTC)
            self.runs[run.id] = run
        state = RunState(run, [item for item in self.attempts.values() if item.run_id == run.id])
        if initialize:
            initialize(state)
        self.save(state)
        return run

    @override
    async def list_runs(self, repo_id: UUID, limit: int | None = 100, *, sha: str | None = None) -> list[WorkflowRun]:
        return [
            run
            for run in reversed(list(self.runs.values()))
            if run.repo_id == repo_id and (sha is None or run.sha == sha)
        ][:limit]

    @override
    async def active_runs(self, repo_id: UUID | None = None) -> list[UUID]:
        return [
            run.id
            for run in self.runs.values()
            if (repo_id is None or run.repo_id == repo_id)
            and (
                run.status in {"running", "queued"}
                or any(
                    message.run_id == run.id and message.kind == "cleanup" and message.acknowledged_at is None
                    for message in self.messages.values()
                )
            )
        ]

    @override
    @asynccontextmanager
    async def transaction(self, run_id: UUID, repo_id: UUID | None = None) -> AsyncGenerator[RunState | None]:

        lock = self.locks.setdefault(run_id, self.lock_factory())
        async with lock:
            token = self.locked_here.set(True)
            try:
                run = self.runs.get(run_id)
                state = (
                    RunState(run, [item for item in self.attempts.values() if item.run_id == run_id])
                    if run and (repo_id is None or run.repo_id == repo_id)
                    else None
                )
                yield state
                if state:
                    self.save(state)
            finally:
                self.locked_here.reset(token)

    @override
    async def message(self, message_id: UUID) -> WorkflowOutbox | None:
        return self.messages.get(message_id)

    @override
    async def pending(self, limit: int = 50) -> list[WorkflowOutbox]:

        cutoff = datetime.now(UTC) - timedelta(seconds=60)
        return sorted(
            [
                item
                for item in self.messages.values()
                if item.acknowledged_at is None and (item.published_at is None or item.published_at < cutoff)
            ],
            key=lambda item: item.due_at,
        )[:limit]

    @override
    async def published(self, message_id: UUID, when: datetime) -> None:
        if message_id in self.messages:
            self.messages[message_id].published_at = when

    @override
    async def current(self, capability: Capability, allow_terminal: bool = False) -> bool:
        attempt, run = self.attempts.get(capability.id), self.runs.get(capability.run)
        statuses = {"queued", "starting", "running"} | ({"success", "failure", "skipped"} if allow_terminal else set())
        return bool(
            attempt
            and run
            and run.repo_id == capability.repo
            and run.status != "cancelled"
            and attempt.fence == capability.fence
            and attempt.generation == capability.generation
            and attempt.status in statuses
            and any(job["id"] == capability.job_id and job.get("attempt_id") == str(capability.id) for job in run.jobs)
        )

    @override
    async def artifacts(self, run_id: UUID) -> list[str]:
        return [
            attempt.artifact_key
            for attempt in self.attempts.values()
            if attempt.run_id == run_id and attempt.artifact_key
        ]


class FakeActionsQueue(ActionsQueue):
    def __init__(self) -> None:
        self.deliveries: list[tuple[str, BaseModel, str, datetime]] = []
        self.verified: list[tuple[str, bytes]] = []
        self.recoveries = 0

    @override
    async def publish(self, operation: str, body: BaseModel, key: str, due_at: datetime) -> None:
        self.deliveries.append((operation, body, key, due_at))

    @override
    async def recover_later(self) -> None:
        self.recoveries += 1

    @override
    def verify(self, operation: str, body: bytes, signature: str) -> None:
        self.verified.append((operation, body))

        if signature != "unit-signed-delivery":
            raise InvalidDeliveryError("Invalid signature")


def compiled_fixture(name: str = "basic") -> CompiledWorkflow:
    path = BACKEND_DIR.parent / "packages/actions-compiler/src/fixtures" / f"{name}.json"
    return CompiledWorkflow.model_validate_json(path.read_text())


class FakeWorkflowCompiler(WorkflowCompiler):
    @override
    async def compile(self, request: CompileRequest) -> CompiledWorkflow:
        return compiled_fixture().model_copy(update={"workflow_name": request.filename})
