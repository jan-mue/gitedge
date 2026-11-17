"""Advance locked workflow runs through sandbox completion callbacks."""

from __future__ import annotations

import asyncio
import logging
import uuid
from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Literal

from app.clients.sandboxes import SandboxError
from app.exceptions import WorkflowError
from app.schemas.actions import ActionJob, ActionStatus
from app.services.actions.inputs import JobInputBuilder
from app.services.actions.runtime import finish_job, redact, update_logs

if TYPE_CHECKING:
    from app.clients.actions import ActionsStore
    from app.clients.blob_storage import BlobStorageClient
    from app.clients.sandboxes import AbstractSandboxClient
    from app.entities.actions import WorkflowRun

logger = logging.getLogger(__name__)
TERMINAL = {ActionStatus.SUCCESS, ActionStatus.FAILURE, ActionStatus.SKIPPED, ActionStatus.CANCELLED}
OPERATION_LEASE = timedelta(minutes=5)


@dataclass
class JobOperation:
    """A leased sandbox operation, recorded privately in the existing job JSON."""

    id: str
    kind: Literal["start", "collect", "delete"]
    job: ActionJob


class RunScheduler:
    """Collect finished jobs and launch ready matrix variants."""

    def __init__(
        self,
        store: ActionsStore,
        blobs: BlobStorageClient,
        sandbox: AbstractSandboxClient,
        max_parallel: int,
        secrets: dict[str, dict[str, str]],
    ) -> None:
        """Inject sandbox, persistence, and concurrency policies."""
        self.store = store
        self.blobs = blobs
        self.sandbox = sandbox
        self.max_parallel = max_parallel
        self.secrets = secrets
        self.inputs = JobInputBuilder()

    async def advance(self, repo_id: uuid.UUID, run_id: uuid.UUID) -> bool:
        """Claim work briefly, perform I/O unlocked, then commit only matching claims."""
        secrets = self.secrets.get(str(repo_id), {})
        visited: set[str] = set()
        cleaned: set[str] = set()
        while True:
            claimed = await self._claim(repo_id, run_id, visited, cleaned)
            if claimed is None:
                return False
            run, operations = claimed
            if not operations:
                return True
            await asyncio.gather(*(self._execute(run, operation, secrets) for operation in operations))
            if not await self._finish(repo_id, run_id, operations):
                return False
            visited.update(operation.job.id for operation in operations if operation.kind != "delete")
            cleaned.update(operation.job.id for operation in operations if operation.kind == "delete")

    async def _claim(
        self, repo_id: uuid.UUID, run_id: uuid.UUID, visited: set[str], cleaned: set[str]
    ) -> tuple[WorkflowRun, list[JobOperation]] | None:
        async with self.store.locked(repo_id, run_id) as run:
            if run is None:
                return None
            now = datetime.now(UTC)
            jobs = [ActionJob.model_validate(job) for job in run.jobs]
            ready = {job.id for job in self._ready(jobs)} if run.status not in TERMINAL else set()
            operations = []
            records = []
            recheck = False
            for job, raw in zip(jobs, run.jobs, strict=True):
                lease = raw.get("_operation")
                if lease and datetime.fromisoformat(lease["expires_at"]) > now:
                    # A callback racing inspection/launch must not be lost: the
                    # claim owner will inspect again after its current I/O completes.
                    if job.status == ActionStatus.RUNNING:
                        records.append({**raw, "_operation": {**lease, "recheck": True}})
                        recheck = True
                    else:
                        records.append(raw)
                    continue
                kind: Literal["start", "collect", "delete"] | None = None
                if job.status in TERMINAL and job.sandbox and job.id not in cleaned:
                    kind = "delete"
                elif job.id not in visited or raw.get("_recheck"):
                    if job.id in ready or (
                        run.status not in TERMINAL
                        and job.status == ActionStatus.RUNNING
                        and lease
                        and lease["kind"] == "start"
                    ):
                        kind = "start"
                        job.started_at = job.started_at or now
                        job.sandbox = f"gitedge-job-{job.id}"
                        job.status = ActionStatus.RUNNING
                    elif job.status == ActionStatus.RUNNING and job.sandbox:
                        kind = "collect"
                record = job.model_dump(mode="json")
                if kind:
                    operation = JobOperation(uuid.uuid4().hex, kind, job)
                    operations.append(operation)
                    record["_operation"] = {
                        "id": operation.id,
                        "kind": kind,
                        "expires_at": (now + OPERATION_LEASE).isoformat(),
                    }
                records.append(record)
            if operations or recheck:
                run.jobs = records
                run.updated_at = now
                if run.status not in TERMINAL:
                    run.status = "running"
            self._update_status(run)
            return deepcopy(run), operations

    async def _execute(self, run: WorkflowRun, operation: JobOperation, secrets: dict[str, str]) -> None:
        job = operation.job
        if operation.kind == "start":
            jobs = [ActionJob.model_validate(raw) for raw in run.jobs]
            await self._start(run, job, jobs, secrets)
        elif operation.kind == "collect":
            await self._collect(run, job, secrets)
        elif job.sandbox:
            try:
                await self.sandbox.delete(job.sandbox)
                job.sandbox = None
            except SandboxError as exc:
                logger.warning("Sandbox cleanup failed for job %s: %s", job.id, redact(str(exc), secrets))

    async def _finish(self, repo_id: uuid.UUID, run_id: uuid.UUID, operations: list[JobOperation]) -> bool:
        async with self.store.locked(repo_id, run_id) as run:
            if run is None:
                return False
            by_id = {operation.job.id: operation for operation in operations}
            records = []
            for raw in run.jobs:
                operation = by_id.get(raw["id"])
                if operation is None or raw.get("_operation", {}).get("id") != operation.id:
                    records.append(raw)
                    continue
                # Cancellation wins over any provider result arriving after it.
                if raw["status"] == ActionStatus.CANCELLED:
                    job = ActionJob.model_validate(raw)
                    if operation.kind == "delete":
                        job.sandbox = operation.job.sandbox
                else:
                    job = operation.job
                record = job.model_dump(mode="json")
                if job.status == ActionStatus.RUNNING and raw["_operation"].get("recheck"):
                    record["_recheck"] = True
                records.append(record)
            run.jobs = records
            run.updated_at = datetime.now(UTC)
            self._update_status(run)
        return True

    @staticmethod
    def _update_status(run: WorkflowRun) -> None:
        if run.status in TERMINAL:
            return
        jobs = [ActionJob.model_validate(raw) for raw in run.jobs]
        finished = all(job.status in TERMINAL and job.sandbox is None for job in jobs)
        failed = any(job.status == ActionStatus.FAILURE and not job.continue_on_error for job in jobs)
        run.status = ("failure" if failed else "success") if finished else "running"
        if finished:
            run.completed_at = datetime.now(UTC)

    def _ready(self, jobs: list[ActionJob]) -> list[ActionJob]:
        available = max(0, self.max_parallel - sum(job.status == ActionStatus.RUNNING for job in jobs))
        pending = {job.key for job in jobs if job.status not in TERMINAL}
        return [job for job in jobs if job.status == ActionStatus.QUEUED and not pending.intersection(job.needs)][
            :available
        ]

    async def _collect(self, run: WorkflowRun, job: ActionJob, secrets: dict[str, str]) -> None:
        if not job.sandbox:
            return
        try:
            if job.status == ActionStatus.RUNNING:
                snapshot = await self.sandbox.inspect(job.sandbox)
                update_logs(job, snapshot.files.get("log.jsonl", b""), secrets)
                if not snapshot.running or "exit-code" in snapshot.files:
                    finish_job(job, snapshot.files, secrets)
                    if state := snapshot.files.get("state.tar.gz"):
                        prefix = f"actions/{run.repo_id}/{run.id}"
                        await self.blobs.put(f"{prefix}/jobs/{job.id}.tar.gz", state)
                        await self.blobs.put(f"{prefix}/state.tar.gz", state)
        except SandboxError as exc:
            self._fail(job, exc, secrets)

    async def _start(
        self,
        run: WorkflowRun,
        job: ActionJob,
        jobs: list[ActionJob],
        secrets: dict[str, str],
    ) -> None:
        job.started_at = job.started_at or datetime.now(UTC)
        job.sandbox = f"gitedge-job-{job.id}"
        job.status = ActionStatus.RUNNING
        try:
            await self.sandbox.start(job.sandbox, self.inputs.build(run, job, jobs, secrets), job.timeout_seconds)
        except (SandboxError, WorkflowError) as exc:
            self._fail(job, exc, secrets)
            try:
                await self.sandbox.delete(job.sandbox)
                job.sandbox = None
            except SandboxError:
                logger.exception("Sandbox cleanup failed after launch for job %s", job.id)

    @staticmethod
    def _fail(job: ActionJob, error: SandboxError | WorkflowError, secrets: dict[str, str]) -> None:
        logger.warning("Sandbox operation failed for job %s: %s", job.id, redact(str(error), secrets))
        job.status = ActionStatus.FAILURE
        job.completed_at = datetime.now(UTC)
        job.error = redact(str(error), secrets)

    async def cancel(self, repo_id: uuid.UUID, run_id: uuid.UUID) -> bool:
        """Persist cancellation before releasing sandbox resources outside the lock."""
        async with self.store.locked(repo_id, run_id) as run:
            if run is None:
                return False
            if run.status in TERMINAL and run.status != ActionStatus.CANCELLED:
                return True
            records = []
            for raw in run.jobs:
                job = ActionJob.model_validate(raw)
                if job.status not in TERMINAL:
                    job.status = ActionStatus.CANCELLED
                    job.completed_at = datetime.now(UTC)
                record = job.model_dump(mode="json")
                if lease := raw.get("_operation"):
                    record["_operation"] = lease
                records.append(record)
            run.status = "cancelled"
            run.completed_at = datetime.now(UTC)
            run.jobs = records
        await self.advance(repo_id, run_id)
        return True
