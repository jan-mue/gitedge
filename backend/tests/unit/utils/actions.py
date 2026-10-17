"""In-memory Actions persistence for unit tests."""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator
    from uuid import UUID

    from app.entities.actions import WorkflowRun


class FakeActionsStore:
    def __init__(self) -> None:
        self.runs: dict[UUID, WorkflowRun] = {}

    async def add_run(self, run: WorkflowRun) -> WorkflowRun:
        for existing in self.runs.values():
            if (existing.repo_id, existing.workflow, existing.event_key) == (run.repo_id, run.workflow, run.event_key):
                return existing
        run.created_at = datetime.now(UTC)
        run.updated_at = run.created_at
        self.runs[run.id] = run
        return run

    async def list_runs(self, repo_id: UUID, limit: int = 100) -> list[WorkflowRun]:
        return [run for run in reversed(list(self.runs.values())) if run.repo_id == repo_id][:limit]

    async def active_runs(self, repo_id: UUID | None = None) -> list[tuple[UUID, UUID]]:
        return [
            (run.repo_id, run.id)
            for run in self.runs.values()
            if run.status in {"running", "queued"} and (repo_id is None or run.repo_id == repo_id)
        ]

    @asynccontextmanager
    async def locked(self, repo_id: UUID, run_id: UUID) -> AsyncGenerator[WorkflowRun | None]:
        run = self.runs.get(run_id)
        yield run if run and run.repo_id == repo_id else None
