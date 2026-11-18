"""Locate workflow source files; language parsing belongs to the Bun compiler."""

import uuid
from typing import TYPE_CHECKING

from app.schemas.actions import ActionJob, ActionStep

if TYPE_CHECKING:
    from app.schemas.workflows import CompiledWorkflow

WORKFLOW_PREFIX = ".gitedge/workflow/"


def workflow_paths(paths: list[str], selected: str | None = None) -> list[str]:
    """Select YAML files directly inside the workflow directory."""
    return [
        path
        for path in paths
        if path.startswith(WORKFLOW_PREFIX)
        and "/" not in path[len(WORKFLOW_PREFIX) :]
        and path.endswith((".yml", ".yaml"))
        and (selected is None or path == selected)
    ]


def instantiate_jobs(compiled: CompiledWorkflow, max_timeout: int) -> list[ActionJob]:
    """Assign resource identities and timeout policy to compiler-produced variants."""
    return [
        ActionJob(
            id=uuid.uuid4().hex,
            key=item.key,
            compiled_id=item.id,
            name=item.name,
            needs=item.needs,
            matrix=item.matrix,
            timeout_seconds=min(item.timeout_seconds, max_timeout),
            continue_on_error=item.continue_on_error,
            steps=[
                ActionStep(
                    id=step.id, name=step.name or (step.uses if step.kind == "action" else f"Run step {index + 1}")
                )
                for index, step in enumerate(item.config.steps)
            ],
        )
        for item in compiled.jobs
    ]
