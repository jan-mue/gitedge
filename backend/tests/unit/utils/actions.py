"""In-memory Actions persistence for unit tests."""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from app.constants import BACKEND_DIR
from app.schemas.workflows import CompiledWorkflow

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator
    from uuid import UUID

    from app.entities.actions import WorkflowCacheEntry, WorkflowRun
    from app.schemas.workflows import CompileRequest


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

    async def runs_for_commit(self, repo_id: UUID, sha: str) -> list[WorkflowRun]:
        return [run for run in await self.list_runs(repo_id, limit=len(self.runs)) if run.sha == sha]

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


class FakeActionsCacheStore:
    def __init__(self) -> None:
        self.entries: dict[tuple[UUID, str, str], WorkflowCacheEntry] = {}

    async def candidates(self, repo_id: UUID, prefix: str, version: str) -> list[WorkflowCacheEntry]:
        return sorted(
            [
                entry
                for entry in self.entries.values()
                if entry.repo_id == repo_id and entry.version == version and entry.key.startswith(prefix)
            ],
            key=lambda entry: entry.updated_at,
            reverse=True,
        )

    async def payload(self, repo_id: UUID, payload_id: UUID) -> WorkflowCacheEntry | None:
        return next(
            (
                entry
                for entry in self.entries.values()
                if entry.repo_id == repo_id and entry.payload_id == payload_id and entry.expires_at > datetime.now(UTC)
            ),
            None,
        )

    async def publish(self, entry: WorkflowCacheEntry, previous: UUID | None) -> WorkflowCacheEntry:
        key = (entry.repo_id, entry.key, entry.version)
        existing = self.entries.get(key)
        if existing and existing.payload_id != previous and existing.expires_at > datetime.now(UTC):
            return existing
        if existing:
            for name in ("payload_id", "size", "checksum", "expires_at"):
                setattr(existing, name, getattr(entry, name))
            entry = existing
        else:
            entry.created_at = datetime.now(UTC)
        entry.updated_at = datetime.now(UTC)
        self.entries[key] = entry
        return entry


def compiled_fixture(name: str = "basic") -> CompiledWorkflow:
    path = BACKEND_DIR.parent / "packages/actions-runner/src/compiler/fixtures" / f"{name}.json"
    return CompiledWorkflow.model_validate_json(path.read_text())


class FakeWorkflowCompiler:
    async def compile(self, request: CompileRequest) -> CompiledWorkflow:
        return compiled_fixture().model_copy(update={"workflow_name": request.filename})
