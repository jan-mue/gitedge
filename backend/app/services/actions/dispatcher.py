"""Execute durable commands outside database transactions."""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from app.clients.sandboxes import AbstractSandboxClient, SandboxError
from app.config import settings
from app.exceptions import ActionsUnavailableError, WorkflowError
from app.schemas.action_dispatch import AttemptIdentity, Capability, Delivery
from app.services.actions.inputs import build_job_input
from app.services.actions.runtime import finish_job, redact, update_logs
from app.services.actions.scheduler import TERMINAL, RunScheduler

if TYPE_CHECKING:
    from app.clients.actions import ActionsStore, RunState
    from app.clients.blob_storage import BlobStorageClient
    from app.clients.qstash import ActionsQueue
    from app.entities.actions import WorkflowAttempt, WorkflowOutbox
    from app.schemas.actions import ActionJob


@dataclass
class ClaimedJob:
    """Detached data needed for provider I/O after a claim commits."""

    run_id: uuid.UUID
    repo_id: uuid.UUID
    attempt_id: uuid.UUID
    claim: uuid.UUID
    identity: AttemptIdentity
    sandbox: str
    job: ActionJob
    files: dict[str, bytes]


class ActionsDispatcher:
    """Execute durable commands without holding database locks."""

    def __init__(
        self,
        store: ActionsStore,
        blobs: BlobStorageClient,
        sandbox: AbstractSandboxClient,
        queue: ActionsQueue,
        scheduler: RunScheduler,
        secrets: dict[str, dict[str, str]],
    ) -> None:
        """Separate durable transitions from sandbox, storage, and broker I/O."""
        self.store, self.blobs, self.sandbox = store, blobs, sandbox
        self.queue, self.scheduler, self.secrets = queue, scheduler, secrets

    async def deliver(self, message: WorkflowOutbox) -> None:
        """Apply one idempotent command from an authenticated delivery."""
        if message.acknowledged_at:
            return
        if message.kind == "cleanup":
            await self._cleanup(message)
        elif work := await self._claim(message):
            try:
                async with asyncio.timeout(settings.ACTIONS_PROVISION_LEASE):
                    if message.kind == "dispatch":
                        await self._start(work)
                    else:
                        await self._inspect(work, message)
            except (SandboxError, TimeoutError) as error:
                await self._retry(work, message, error)
        await self.flush()

    async def _claim(self, message: WorkflowOutbox) -> ClaimedJob | None:
        async with self.store.transaction(message.run_id) as state:
            if state is None:
                return None
            attempt = state.attempt(message.attempt_id)
            job = state.job(attempt) if attempt else None
            if not attempt or not job or job.status in TERMINAL:
                state.acknowledged.append(message.id)
                return None
            now = datetime.now(UTC)
            if message.kind == "dispatch" and attempt.status != "queued":
                state.acknowledged.append(message.id)
                return None
            if attempt.lease_until and attempt.lease_until > now:
                raise ActionsUnavailableError("Job operation is leased")
            if attempt.status == "starting":
                self.scheduler.fail(state, attempt, "Sandbox provisioning lease expired")
                state.acknowledged.append(message.id)
                return None
            claim = uuid.uuid4()
            attempt.claim, attempt.lease_until = claim, now + timedelta(seconds=settings.ACTIONS_PROVISION_LEASE)
            files = {}
            if message.kind == "dispatch":
                attempt.status = "starting"
                attempt.deadline = now + timedelta(seconds=job.timeout_seconds + settings.ACTIONS_PROVISION_LEASE)
                job.started_at = now
                state.acknowledged.append(message.id)
                state.enqueue("inspect", attempt, settings.ACTIONS_PROVISION_LEASE + 1, key=f"launch:{claim}")
                try:
                    files = build_job_input(state.run, job, state.jobs, self._secrets(state.run.repo_id), attempt)
                except WorkflowError as error:
                    attempt.claim, attempt.lease_until = None, None
                    self.scheduler.fail(state, attempt, str(error), retry=False)
                    return None
            return ClaimedJob(
                state.run.id,
                state.run.repo_id,
                attempt.id,
                claim,
                AttemptIdentity(id=attempt.id, job_id=job.id, generation=attempt.generation, fence=attempt.fence),
                attempt.sandbox,
                job.model_copy(deep=True),
                files,
            )

    async def _start(self, work: ClaimedJob) -> None:
        await self.sandbox.start(work.sandbox, work.files, work.job.timeout_seconds)
        accepted = False
        async with self.store.transaction(work.run_id) as state:
            if state and (attempt := self._owned(state, work)):
                attempt.status, attempt.claim, attempt.lease_until = "running", None, None
                self.scheduler.inspect_later(state, attempt, 0)
                accepted = True
        if not accepted:
            await self.sandbox.delete(work.sandbox)

    async def _inspect(self, work: ClaimedJob, message: WorkflowOutbox) -> None:
        snapshot = await self.sandbox.inspect(work.sandbox)
        secrets = self._secrets(work.repo_id)
        update_logs(work.job, snapshot.files.get("log.jsonl", b""), secrets, work.identity)
        finished = not snapshot.running or "exit-code" in snapshot.files
        artifact_key = None
        if finished:
            finish_job(work.job, snapshot.files, secrets, work.identity)
            if archive := snapshot.files.get("state.tar.gz"):
                artifact_key = f"actions/{work.repo_id}/{work.run_id}/attempts/{work.attempt_id}/state.tar.gz"
                await self.blobs.put(artifact_key, archive)
        async with self.store.transaction(work.run_id) as state:
            if state and (attempt := self._owned(state, work)):
                if finished:
                    self.scheduler.finish(state, attempt, work.job, artifact_key)
                elif datetime.now(UTC) >= attempt.deadline:
                    self.scheduler.fail(state, attempt, "Job exceeded timeout-minutes", retry=False)
                else:
                    state.jobs = [work.job if item.id == work.job.id else item for item in state.jobs]
                    attempt.claim, attempt.lease_until = None, None
                    self.scheduler.inspect_later(state, attempt)
            if state:
                state.acknowledged.append(message.id)

    async def _retry(self, work: ClaimedJob, message: WorkflowOutbox, error: Exception) -> None:
        async with self.store.transaction(work.run_id) as state:
            if state and (attempt := self._owned(state, work)):
                if message.kind == "dispatch":
                    self.scheduler.fail(state, attempt, redact(str(error), self._secrets(work.repo_id)))
                else:
                    attempt.claim, attempt.lease_until = None, None
                    if datetime.now(UTC) >= attempt.deadline:
                        self.scheduler.fail(state, attempt, "Job exceeded timeout-minutes", retry=False)
                        state.acknowledged.append(message.id)
        if message.kind != "dispatch":
            raise ActionsUnavailableError("Sandbox collection must be retried") from error

    async def _cleanup(self, message: WorkflowOutbox) -> None:
        sandbox = None
        async with self.store.transaction(message.run_id) as state:
            attempt = state.attempt(message.attempt_id) if state else None
            if attempt:
                sandbox = attempt.sandbox
        if not sandbox:
            return
        try:
            await self.sandbox.delete(sandbox)
        except SandboxError as error:
            raise ActionsUnavailableError("Sandbox cleanup must be retried") from error
        async with self.store.transaction(message.run_id) as state:
            if state and (attempt := state.attempt(message.attempt_id)):
                if (job := state.job(attempt)) and job.status in TERMINAL:
                    job.sandbox = None
                if attempt.lease_until and attempt.lease_until > datetime.now(UTC):
                    delay = (attempt.lease_until - datetime.now(UTC)).total_seconds() + 1
                    state.enqueue("cleanup", attempt, delay, key="after-lease")
                state.acknowledged.append(message.id)
                self.scheduler.advance(state)

    async def notify(self, capability: Capability) -> None:
        """Queue collection of a completed attempt."""
        async with self.store.transaction(capability.run, capability.repo) as state:
            if state and (attempt := state.attempt(capability.id)) and attempt.status in {"starting", "running"}:
                state.enqueue("inspect", attempt, key="completion")
        await self.flush()

    async def cancel(self, repo_id: uuid.UUID, run_id: uuid.UUID) -> bool:
        """Commit cancellation before publishing resource cleanup."""
        async with self.store.transaction(run_id, repo_id) as state:
            if state is None:
                return False
            self.scheduler.cancelled(state)
        await self.flush()
        return True

    async def reconcile(self) -> None:
        """Recover stalled commands and leases through QStash."""
        await self.queue.recover_later()
        for run_id in await self.store.active_runs():
            async with self.store.transaction(run_id) as state:
                if state:
                    self.scheduler.recover(state)
        await self.flush()

    async def flush(self) -> None:
        """Publish a bounded page of committed outbox commands."""
        try:
            async with asyncio.timeout(15):
                for message in await self.store.pending(limit=25):
                    now = datetime.now(UTC)
                    await self.queue.publish(
                        message.kind,
                        Delivery(id=message.id),
                        f"{message.id}:{int(now.timestamp()) // 60}",
                        message.due_at,
                    )
                    await self.store.published(message.id, now)
        except TimeoutError as error:
            raise ActionsUnavailableError("Outbox publishing must be retried") from error

    @staticmethod
    def _owned(state: RunState, work: ClaimedJob) -> WorkflowAttempt | None:
        attempt = state.attempt(work.attempt_id)
        job = state.job(attempt) if attempt else None
        return attempt if attempt and job and job.status not in TERMINAL and attempt.claim == work.claim else None

    def _secrets(self, repo_id: uuid.UUID) -> dict[str, str]:
        return self.secrets.get(str(repo_id), {})
