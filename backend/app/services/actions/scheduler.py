"""Advance locked workflow runs through sandbox completion callbacks."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from app.clients.sandboxes import SandboxError
from app.schemas.actions import ActionJob, ActionStatus
from app.services.actions.inputs import JobInputBuilder
from app.services.actions.runtime import finish_job, redact, update_logs

if TYPE_CHECKING:
    import uuid

    from app.clients.actions import ActionsStore
    from app.clients.blob_storage import BlobStorageClient
    from app.clients.sandboxes import AbstractSandboxClient
    from app.entities.actions import WorkflowRun

logger = logging.getLogger(__name__)
TERMINAL = {ActionStatus.SUCCESS, ActionStatus.FAILURE, ActionStatus.SKIPPED, ActionStatus.CANCELLED}


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
        """Collect, clean up, and schedule under one run lock."""
        async with self.store.locked(repo_id, run_id) as run:
            if run is None:
                return False
            if run.status in TERMINAL:
                return True
            run.updated_at = datetime.now(UTC)
            secrets = self.secrets.get(str(repo_id), {})
            jobs = [ActionJob.model_validate(job) for job in run.jobs]
            for job in jobs:
                await self._collect(run, job, secrets)
            while ready := self._ready(jobs):
                await asyncio.gather(*(self._start(run, job, jobs, secrets) for job in ready))
            run.jobs = [job.model_dump(mode="json") for job in jobs]
            finished = all(job.status in TERMINAL and job.sandbox is None for job in jobs)
            failed = any(job.status == ActionStatus.FAILURE and not job.continue_on_error for job in jobs)
            run.status = ("failure" if failed else "success") if finished else "running"
            if finished:
                run.completed_at = datetime.now(UTC)
        return True

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
            if job.status in TERMINAL:
                await self.sandbox.delete(job.sandbox)
                job.sandbox = None
        except SandboxError as exc:
            self._fail(job, exc, secrets)

    async def _start(
        self,
        run: WorkflowRun,
        job: ActionJob,
        jobs: list[ActionJob],
        secrets: dict[str, str],
    ) -> None:
        job.started_at = datetime.now(UTC)
        job.sandbox = f"gitedge-job-{job.id}"
        job.status = ActionStatus.RUNNING
        try:
            await self.sandbox.start(job.sandbox, self.inputs.build(run, job, jobs, secrets), job.timeout_seconds)
        except SandboxError as exc:
            self._fail(job, exc, secrets)
            try:
                await self.sandbox.delete(job.sandbox)
                job.sandbox = None
            except SandboxError:
                logger.exception("Sandbox cleanup failed after launch for job %s", job.id)

    @staticmethod
    def _fail(job: ActionJob, error: SandboxError, secrets: dict[str, str]) -> None:
        logger.warning("Sandbox operation failed for job %s: %s", job.id, redact(str(error), secrets))
        job.status = ActionStatus.FAILURE
        job.completed_at = datetime.now(UTC)
        job.error = redact(str(error), secrets)

    async def cancel(self, repo_id: uuid.UUID, run_id: uuid.UUID) -> bool:
        """Cancel active jobs and release their sandbox handles."""
        async with self.store.locked(repo_id, run_id) as run:
            if run is None:
                return False
            if run.status in TERMINAL:
                return True
            jobs = [ActionJob.model_validate(job) for job in run.jobs]
            for job in jobs:
                if job.status not in TERMINAL:
                    job.status = ActionStatus.CANCELLED
                    job.completed_at = datetime.now(UTC)
                if job.sandbox:
                    await self.sandbox.delete(job.sandbox)
                    job.sandbox = None
            run.status = "cancelled"
            run.completed_at = datetime.now(UTC)
            run.jobs = [job.model_dump(mode="json") for job in jobs]
        return True
