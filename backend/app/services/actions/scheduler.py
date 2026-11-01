"""Pure run transitions; provider and queue I/O belong to the dispatcher."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from app.config import settings
from app.entities.actions import WorkflowAttempt
from app.schemas.actions import ActionJob, ActionStatus

if TYPE_CHECKING:
    from app.clients.actions import RunState

TERMINAL = {ActionStatus.SUCCESS, ActionStatus.FAILURE, ActionStatus.SKIPPED, ActionStatus.CANCELLED}


class RunScheduler:
    """Choose state transitions without performing external I/O."""

    def __init__(self, max_parallel: int) -> None:
        """Limit the number of job reservations in each run."""
        self.max_parallel = max_parallel

    def advance(self, state: RunState) -> None:
        """Reserve ready jobs and settle fully cleaned runs."""
        if state.run.status in TERMINAL:
            return
        pending = {job.key for job in state.jobs if job.status not in TERMINAL or job.sandbox}
        available = self.max_parallel - sum(job.status == ActionStatus.RUNNING for job in state.jobs)
        for job in state.jobs:
            if available <= 0:
                break
            if job.status != ActionStatus.QUEUED or pending.intersection(job.needs):
                continue
            attempt_id = uuid.uuid4()
            generation = max((item.generation for item in state.attempts if item.job_id == job.id), default=0) + 1
            attempt = WorkflowAttempt(
                id=attempt_id,
                run_id=state.run.id,
                job_id=job.id,
                generation=generation,
                fence=uuid.uuid4(),
                sandbox=f"gitedge-attempt-{attempt_id.hex}",
                status="queued",
                log_seq=0,
                deadline=datetime.now(UTC) + timedelta(seconds=job.timeout_seconds + settings.ACTIONS_PROVISION_LEASE),
            )
            state.attempts.append(attempt)
            job.attempt_id, job.sandbox, job.status = attempt.id, attempt.sandbox, ActionStatus.RUNNING
            job.error = None
            state.enqueue("dispatch", attempt)
            available -= 1
        if all(job.status in TERMINAL and not job.sandbox for job in state.jobs):
            state.run.status = (
                "failure"
                if any(job.status == ActionStatus.FAILURE and not job.continue_on_error for job in state.jobs)
                else "success"
            )
            state.run.completed_at = datetime.now(UTC)
        else:
            state.run.status = "running"

    def fail(self, state: RunState, attempt: WorkflowAttempt, error: str, retry: bool = True) -> None:
        """Bound infrastructure retries and fence the previous generation."""
        job = state.job(attempt)
        if not job:
            return
        attempt.status, attempt.completed_at, attempt.error = "failure", datetime.now(UTC), error
        state.enqueue("cleanup", attempt)
        job.error = error
        if retry and attempt.generation < settings.ACTIONS_MAX_ATTEMPTS:
            job.status, job.sandbox, job.attempt_id = ActionStatus.QUEUED, None, None
            job.started_at, job.completed_at = None, None
            job.outputs = {}
            for step in job.steps:
                step.status = ActionStatus.QUEUED
        else:
            job.status, job.completed_at = ActionStatus.FAILURE, datetime.now(UTC)
        self.advance(state)

    def finish(self, state: RunState, attempt: WorkflowAttempt, job: ActionJob, artifact_key: str | None) -> None:
        """Publish one current result and queue sandbox cleanup."""
        if state.job(attempt) is None:
            return
        attempt.status, attempt.completed_at = job.status.value, datetime.now(UTC)
        attempt.artifact_key, attempt.error = artifact_key, job.error
        state.jobs = [job if item.id == job.id else item for item in state.jobs]
        state.enqueue("cleanup", attempt)
        self.advance(state)

    def cancelled(self, state: RunState) -> None:
        """Revoke attempts and enqueue cleanup without provider calls."""
        if state.run.status in TERMINAL:
            return
        state.run.status, state.run.completed_at = "cancelled", datetime.now(UTC)
        for job in state.jobs:
            if job.status not in TERMINAL:
                job.status, job.completed_at = ActionStatus.CANCELLED, datetime.now(UTC)
            if job.attempt_id and (attempt := state.attempt(job.attempt_id)):
                attempt.status, attempt.completed_at = "cancelled", datetime.now(UTC)
                state.enqueue("cleanup", attempt)

    def recover(self, state: RunState) -> None:
        """Recover expired provisioning leases and stalled collection."""
        now = datetime.now(UTC)
        for job in state.jobs:
            if job.status != ActionStatus.RUNNING or job.attempt_id:
                continue
            job.status, job.completed_at = ActionStatus.FAILURE, now
            job.error = "Legacy execution has no attempt identity; dispatch a new run"
            if job.sandbox:
                attempt = WorkflowAttempt(
                    id=uuid.uuid4(),
                    run_id=state.run.id,
                    job_id=job.id,
                    generation=1,
                    fence=uuid.uuid4(),
                    sandbox=job.sandbox,
                    status="failure",
                    deadline=now,
                    completed_at=now,
                )
                state.attempts.append(attempt)
                job.attempt_id = attempt.id
                state.enqueue("cleanup", attempt)
        for attempt in list(state.attempts):
            if not state.job(attempt):
                continue
            if attempt.status == "starting" and attempt.lease_until and attempt.lease_until <= now:
                self.fail(state, attempt, "Sandbox provisioning lease expired")
            elif attempt.status == "running":
                self.inspect_later(state, attempt, 0)
        self.advance(state)

    @staticmethod
    def inspect_later(state: RunState, attempt: WorkflowAttempt, delay: int | None = None) -> None:
        """Schedule a distinct collection command for its delivery window."""
        interval = settings.ACTIONS_INSPECT_INTERVAL
        wait = interval if delay is None else delay
        slot = int(datetime.now(UTC).timestamp() + wait) // interval
        state.enqueue("inspect", attempt, wait, key=str(slot))
