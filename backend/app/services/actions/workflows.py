"""Workflow discovery, event filters, DAG validation, and matrix expansion."""

import itertools
import re
import uuid
from graphlib import CycleError, TopologicalSorter
from typing import Any

import yaml
from pydantic import ValidationError

from app.schemas.actions import ActionJob, ActionStep, WorkflowInfo
from app.schemas.workflow_events import PullRequestEvent, ScheduleEvent, WorkflowEvent
from app.schemas.workflows import EventFilters, WorkflowJob

MAX_JOBS = 256
WORKFLOW_PREFIX = ".gitedge/workflow/"


class WorkflowError(ValueError):
    """A workflow cannot be scheduled safely or is outside supported syntax."""


class WorkflowLoader(yaml.SafeLoader):
    """Use YAML 1.2 boolean spelling so the Actions `on` key stays a string."""


WorkflowLoader.yaml_implicit_resolvers = {
    key: [(tag, expression) for tag, expression in values if tag != "tag:yaml.org,2002:bool"]
    for key, values in yaml.SafeLoader.yaml_implicit_resolvers.items()
}
WorkflowLoader.add_implicit_resolver(
    "tag:yaml.org,2002:bool", re.compile(r"^(?:true|false|True|False|TRUE|FALSE)$"), list("tTfF")
)


def parse_workflow(raw: str) -> dict[str, Any]:
    """Parse ordinary GitHub/Gitea YAML and bound its orchestration size."""
    if len(raw) > 1024 * 1024:
        raise WorkflowError("Workflow exceeds 1 MiB")
    try:
        result = yaml.load(raw, Loader=WorkflowLoader)  # noqa: S506 - subclass of SafeLoader with YAML 1.2 booleans
    except yaml.YAMLError as exc:
        raise WorkflowError(f"Invalid workflow YAML: {exc}") from exc
    if not isinstance(result, dict) or not isinstance(result.get("jobs"), dict) or not result["jobs"]:
        raise WorkflowError("Workflow must define jobs")
    return result


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


def workflow_info(path: str, definition: dict[str, Any]) -> WorkflowInfo:
    """Describe a workflow without exposing its source or secrets."""
    trigger = definition.get("on", {})
    return WorkflowInfo(
        path=path,
        name=str(definition.get("name", path.rsplit("/", 1)[-1])),
        dispatch="workflow_dispatch" in (trigger if isinstance(trigger, dict | list) else [trigger]),
    )


def _glob(pattern: str) -> re.Pattern[str]:
    # GitHub path/branch globs: * stays within a segment, ** crosses segments.
    expression = re.escape(pattern)
    expression = (
        expression.replace(r"\*\*/", "(?:.*/)?").replace(r"\*\*", ".*").replace(r"\*", "[^/]*").replace(r"\?", "[^/]")
    )
    return re.compile(f"^{expression}$")


def _matches(value: str, patterns: list[str]) -> bool:
    matched = False
    for pattern in patterns:
        excluded = pattern.startswith("!")
        if _glob(pattern[1:] if excluded else pattern).match(value):
            matched = not excluded
    return matched


def matches_event(definition: dict[str, Any], event: WorkflowEvent) -> bool:
    """Match event activity, refs, and changed files against workflow filters."""
    triggers = definition.get("on", {})
    if isinstance(triggers, str | list):
        return event.event_name in (triggers if isinstance(triggers, list) else [triggers])
    if not isinstance(triggers, dict) or event.event_name not in triggers:
        return False
    if isinstance(event, ScheduleEvent):
        return any(item.get("cron") == event.schedule for item in (triggers[event.event_name] or []))
    try:
        filters = EventFilters.model_validate(triggers[event.event_name] or {})
    except ValidationError as exc:
        raise WorkflowError(f"Invalid event filters: {exc}") from exc
    if filters.types and (not isinstance(event, PullRequestEvent) or event.action not in filters.types):
        return False
    tag = event.ref.startswith("refs/tags/")
    included, excluded, other = (
        (filters.tags, filters.tags_ignore, filters.branches)
        if tag
        else (filters.branches, filters.branches_ignore, filters.tags)
    )
    ref = event.pull_request.base.ref if isinstance(event, PullRequestEvent) else event.ref
    ref = ref.removeprefix("refs/heads/").removeprefix("refs/tags/")
    return (
        not (other and not included)
        and (not included or _matches(ref, included))
        and not (excluded and _matches(ref, excluded))
        and (tag or _matches_paths(event.changed_paths, filters))
    )


def _matches_paths(paths: list[str], filters: EventFilters) -> bool:
    if filters.paths is not None and not any(_matches(path, filters.paths) for path in paths):
        return False
    return not (
        filters.paths_ignore is not None and paths and all(_matches(path, filters.paths_ignore) for path in paths)
    )


def expand_matrix(strategy: dict[str, Any]) -> list[dict[str, Any]]:
    """Expand cartesian axes with GitHub include/exclude semantics."""
    matrix = strategy.get("matrix", {})
    if not isinstance(matrix, dict):
        raise WorkflowError("Dynamic matrices are not supported yet; use a literal strategy.matrix")
    axes = {key: value for key, value in matrix.items() if key not in {"include", "exclude"}}
    if any(not isinstance(values, list) for values in axes.values()):
        raise WorkflowError("Matrix axes must be arrays")
    count = 1
    for values in axes.values():
        count *= len(values)
        if count > MAX_JOBS:
            raise WorkflowError("Matrix exceeds 256 jobs")
    original = [dict(zip(axes, values, strict=True)) for values in itertools.product(*axes.values())] if axes else []
    original = [
        item
        for item in original
        if not any(
            all(item.get(key) == value for key, value in exclude.items()) for exclude in matrix.get("exclude", [])
        )
    ]
    expanded = [dict(item) for item in original]
    extras = []
    for include in matrix.get("include", []):
        merged = False
        for source, target in zip(original, expanded, strict=True):
            if all(key not in source or source[key] == value for key, value in include.items()):
                target.update(include)
                merged = True
        if not merged:
            extras.append(include)
    return [*expanded, *extras] if axes or matrix.get("include") else [{}]


def plan_jobs(definition: dict[str, Any], max_timeout: int) -> list[ActionJob]:
    """Validate the dependency graph and allocate each matrix variant."""
    try:
        jobs = {key: WorkflowJob.model_validate(value) for key, value in definition["jobs"].items()}
    except ValidationError as exc:
        raise WorkflowError(f"Invalid job definition: {exc}") from exc
    for key, job in jobs.items():
        if any(need not in jobs for need in job.needs):
            raise WorkflowError(f"Unknown dependency in job {key}")
    try:
        tuple(TopologicalSorter({key: job.needs for key, job in jobs.items()}).static_order())
    except CycleError as exc:
        raise WorkflowError("Workflow dependency graph contains a cycle") from exc
    result: list[ActionJob] = []
    for key, job in jobs.items():
        for matrix in expand_matrix(job.strategy):
            suffix = f" ({', '.join(str(value) for value in matrix.values())})" if matrix else ""
            result.append(
                ActionJob(
                    id=uuid.uuid4().hex,
                    key=key,
                    name=(job.name or key) + suffix,
                    needs=job.needs,
                    matrix=matrix,
                    timeout_seconds=min(max(1, int(job.timeout_minutes * 60)), max_timeout),
                    continue_on_error=job.continue_on_error is True,
                    steps=[
                        ActionStep(id=step.id or str(index), name=step.name or step.uses or f"Run step {index + 1}")
                        for index, step in enumerate(job.steps)
                    ],
                )
            )
        if len(result) > MAX_JOBS:
            raise WorkflowError("Workflow exceeds 256 expanded jobs")
    return result
