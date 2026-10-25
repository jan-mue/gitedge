"""In-memory Actions persistence for unit tests."""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import TYPE_CHECKING, override

from app.clients.actions import ActionsStore
from app.clients.workflow_compiler import WorkflowCompiler
from app.constants import BACKEND_DIR
from app.schemas.workflows import CompiledWorkflow

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator
    from uuid import UUID

    from app.entities.actions import WorkflowRun
    from app.schemas.workflows import CompileRequest


class FakeActionsStore(ActionsStore):
    def __init__(self) -> None:
        self.runs: dict[UUID, WorkflowRun] = {}

    @override
    async def add_run(self, run: WorkflowRun) -> WorkflowRun:
        for existing in self.runs.values():
            if (existing.repo_id, existing.workflow, existing.event_key) == (run.repo_id, run.workflow, run.event_key):
                return existing
        run.created_at = datetime.now(UTC)
        run.updated_at = run.created_at
        self.runs[run.id] = run
        return run

    @override
    async def list_runs(self, repo_id: UUID, limit: int = 100) -> list[WorkflowRun]:
        return [run for run in reversed(list(self.runs.values())) if run.repo_id == repo_id][:limit]

    @override
    async def runs_for_commit(self, repo_id: UUID, sha: str) -> list[WorkflowRun]:
        return [run for run in await self.list_runs(repo_id, limit=len(self.runs)) if run.sha == sha]

    @override
    async def active_runs(self, repo_id: UUID | None = None) -> list[tuple[UUID, UUID]]:
        return [
            (run.repo_id, run.id)
            for run in self.runs.values()
            if run.status in {"running", "queued"} and (repo_id is None or run.repo_id == repo_id)
        ]

    @override
    @asynccontextmanager
    async def locked(self, repo_id: UUID, run_id: UUID) -> AsyncGenerator[WorkflowRun | None]:
        run = self.runs.get(run_id)
        yield run if run and run.repo_id == repo_id else None


def compiled_fixture(name: str = "basic") -> CompiledWorkflow:
    path = BACKEND_DIR.parent / "packages/actions-runner/src/compiler/fixtures" / f"{name}.json"
    return CompiledWorkflow.model_validate_json(path.read_text())


class FakeWorkflowCompiler(WorkflowCompiler):
    @override
    async def compile(self, request: CompileRequest) -> CompiledWorkflow:
        return compiled_fixture().model_copy(update={"workflow_name": request.filename})
