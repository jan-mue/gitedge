"""Build sandbox descriptors and scoped access capabilities."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import ValidationError

from app.config import settings
from app.exceptions import WorkflowError
from app.schemas.action_dispatch import AttemptIdentity
from app.schemas.workflow_events import workflow_event_adapter
from app.schemas.workflows import CompiledWorkflow, JobDependency, JobInput, WorkflowContext
from app.services.actions.capabilities import issue_capability

if TYPE_CHECKING:
    from app.entities.actions import WorkflowAttempt, WorkflowRun
    from app.schemas.actions import ActionJob


def build_job_input(
    run: WorkflowRun, job: ActionJob, jobs: list[ActionJob], secrets: dict[str, str], attempt: WorkflowAttempt
) -> dict[str, bytes]:
    """Include dependency results and short-lived repository/run capabilities."""
    event = workflow_event_adapter.validate_python({**run.event, "event_name": run.event_name})
    if event.repository is None:
        raise ValueError("Workflow event must identify its repository")
    repository = event.repository.full_name
    if run.compiled is None:
        raise WorkflowError("Workflow run has no compiled manifest; dispatch a new run")
    try:
        compiled = CompiledWorkflow.model_validate(run.compiled)
    except ValidationError as error:
        raise WorkflowError("Workflow has an incompatible compiled manifest; dispatch a new run") from error
    specification = next((item for item in compiled.jobs if item.id == job.compiled_id), None)
    if specification is None:
        raise WorkflowError("Compiled job variant is missing from the persisted plan")
    server = settings.ACTIONS_SERVER_URL
    payload = JobInput(
        attempt=AttemptIdentity(id=attempt.id, job_id=job.id, generation=attempt.generation, fence=attempt.fence),
        workflow=WorkflowContext(name=compiled.workflow_name, env=compiled.env, defaults=compiled.defaults),
        job=specification,
        inputs=compiled.inputs,
        timeout_seconds=job.timeout_seconds,
        needs=_dependencies(job, jobs),
        event_name=run.event_name,
        event=run.event,
        actor=run.actor,
        env={
            "GITHUB_RUN_ID": str(run.id.int & ((1 << 63) - 1)),
            "GITHUB_RUN_NUMBER": str(int(run.created_at.timestamp())),
            "GITHUB_REPOSITORY": repository,
            "GITHUB_REPOSITORY_OWNER": repository.split("/")[0],
            "GITHUB_REF": run.ref,
            "GITHUB_SHA": run.sha,
            "GITHUB_SERVER_URL": server,
            "GITHUB_API_URL": server + "/api/v1",
        },
        secrets={**secrets, "GITHUB_TOKEN": issue_capability(run, job, attempt, "git:read")},
        restore_url=_callback(run, job, attempt, "state"),
        report_url=f"{server}/api/v1/actions/attempts/{attempt.id}",
        report_token=issue_capability(run, job, attempt, "actions:report"),
        cache_url=_callback(run, job, attempt, "cache"),
    )
    return {"input.json": payload.model_dump_json(by_alias=True, exclude_none=True).encode()}


def _dependencies(job: ActionJob, jobs: list[ActionJob]) -> dict[str, JobDependency]:
    result = {}
    for key in job.needs:
        parents = [parent for parent in jobs if parent.key == key]
        status = next(
            (
                status
                for status in ("failure", "cancelled", "skipped")
                if any(parent.status == status and not parent.continue_on_error for parent in parents)
            ),
            "success",
        )
        result[key] = JobDependency(
            result=status, outputs={name: value for parent in parents for name, value in parent.outputs.items()}
        )
    return result


def _callback(run: WorkflowRun, job: ActionJob, attempt: WorkflowAttempt, purpose: str) -> str:
    token = issue_capability(run, job, attempt, f"actions:{purpose}")
    return f"{settings.ACTIONS_SERVER_URL}/api/v1/actions/{purpose}?token={token}"
