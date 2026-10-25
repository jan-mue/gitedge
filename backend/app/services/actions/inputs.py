"""Build sandbox descriptors and scoped access capabilities."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import jwt

from app.config import settings
from app.exceptions import WorkflowError
from app.schemas.workflow_events import workflow_event_adapter
from app.schemas.workflows import CompiledWorkflow, JobDependency, JobInput, WorkflowContext
from app.utils import security

if TYPE_CHECKING:
    from app.entities.actions import WorkflowRun
    from app.schemas.actions import ActionJob


class JobInputBuilder:
    """Translate persisted runs into the runner input contract."""

    def build(
        self, run: WorkflowRun, job: ActionJob, jobs: list[ActionJob], secrets: dict[str, str]
    ) -> dict[str, bytes]:
        """Include dependency results and short-lived repository/run capabilities."""
        event = workflow_event_adapter.validate_python({**run.event, "event_name": run.event_name})
        if event.repository is None:
            raise ValueError("Workflow event must identify its repository")
        repository = event.repository.full_name
        if run.compiled is None:
            raise WorkflowError("Workflow run predates manifest version 1; dispatch a new run")
        compiled = CompiledWorkflow.model_validate(run.compiled)
        specification = next((item for item in compiled.jobs if item.id == job.compiled_id), None)
        if specification is None:
            raise WorkflowError("Compiled job variant is missing from the persisted plan")
        server = settings.ACTIONS_SERVER_URL
        payload = JobInput(
            workflow=WorkflowContext(name=compiled.workflow_name, env=compiled.env, defaults=compiled.defaults),
            job=specification,
            inputs=compiled.inputs,
            timeout_seconds=job.timeout_seconds,
            needs=self._dependencies(job, jobs),
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
            secrets={**secrets, "GITHUB_TOKEN": self._token(run, job, "git:read")},
            restore_url=self._callback(run, job, "state"),
            complete_url=self._callback(run, job, "complete"),
        )
        return {"input.json": payload.model_dump_json(by_alias=True, exclude_none=True).encode()}

    @staticmethod
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

    def _callback(self, run: WorkflowRun, job: ActionJob, purpose: str) -> str:
        token = self._token(run, job, f"actions:{purpose}")
        return f"{settings.ACTIONS_SERVER_URL}/api/v1/actions/{purpose}?token={token}"

    @staticmethod
    def _token(run: WorkflowRun, job: ActionJob, scope: str) -> str:
        return jwt.encode(
            {
                "sub": "actions",
                "repo": str(run.repo_id),
                "run": str(run.id),
                "scope": scope,
                "exp": datetime.now(UTC) + timedelta(seconds=job.timeout_seconds + 60),
            },
            settings.SECRET_KEY,
            algorithm=security.ALGORITHM,
        )
