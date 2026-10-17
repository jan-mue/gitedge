"""Workflow discovery, event filters, DAG validation, and matrix expansion."""

import itertools
import math
import re
import uuid
from typing import Any

import yaml

from app.schemas.actions import ActionJob, ActionStep, WorkflowInfo

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


def matches_event(definition: dict[str, Any], event_name: str, event: dict[str, Any]) -> bool:  # noqa: PLR0911
    """Apply event names, activity types, branch/tag filters, and changed paths."""
    triggers = definition.get("on", {})
    if isinstance(triggers, str | list):
        return event_name in (triggers if isinstance(triggers, list) else [triggers])
    if not isinstance(triggers, dict) or event_name not in triggers:
        return False
    if event_name == "schedule":
        return any(item.get("cron") == event.get("schedule") for item in (triggers[event_name] or []))
    options = triggers[event_name] or {}
    if not isinstance(options, dict):
        raise WorkflowError("Event filters must be a mapping")
    if options.get("types") and event.get("action") not in options["types"]:
        return False
    ref = str(event.get("ref", ""))
    group = "tags" if ref.startswith("refs/tags/") else "branches"
    other = "branches" if group == "tags" else "tags"
    ref_name = ref.removeprefix("refs/heads/").removeprefix("refs/tags/")
    if event_name == "pull_request":
        ref_name = event.get("pull_request", {}).get("base", {}).get("ref", ref_name)
    if options.get(other) and not options.get(group):
        return False
    if options.get(group) and not _matches(ref_name, options[group]):
        return False
    if options.get(f"{group}-ignore") and _matches(ref_name, options[f"{group}-ignore"]):
        return False
    if group == "tags":
        return True
    paths = event.get("changed_paths", [])
    if "paths" in options and not any(_matches(path, options["paths"]) for path in paths):
        return False
    return not ("paths-ignore" in options and paths and all(_matches(path, options["paths-ignore"]) for path in paths))


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


def plan_jobs(definition: dict[str, Any], max_timeout: int) -> list[ActionJob]:  # noqa: PLR0912
    """Validate the dependency graph and allocate one stable id per matrix job."""
    jobs = definition["jobs"]
    result: list[ActionJob] = []
    dependencies: dict[str, list[str]] = {}
    for key, job in jobs.items():
        if not isinstance(key, str) or not isinstance(job, dict):
            raise WorkflowError("Job ids must map to job definitions")
        needs = job.get("needs", [])
        needs = [needs] if isinstance(needs, str) else needs
        if not isinstance(needs, list) or any(need not in jobs for need in needs):
            raise WorkflowError(f"Unknown dependency in job {key}")
        dependencies[key] = needs
        if job.get("uses") or job.get("container") or job.get("services"):
            raise WorkflowError(
                "Reusable workflows, job containers, and service containers are not supported inside isolated job sandboxes"
            )
        if not isinstance(job.get("steps"), list) or not job["steps"]:
            raise WorkflowError(f"Job {key} must contain steps")
        if any(not isinstance(step, dict) or (("run" in step) == ("uses" in step)) for step in job["steps"]):
            raise WorkflowError(f"Each step in job {key} must define exactly one of run or uses")
        if any(str(step.get("uses", "")).startswith("docker://") for step in job["steps"]):
            raise WorkflowError("Docker actions require nested Docker and are not supported")
        try:
            duration = float(job.get("timeout-minutes", 20))
        except (ValueError, TypeError) as exc:
            raise WorkflowError(f"Invalid timeout-minutes in job {key}") from exc
        if not math.isfinite(duration) or duration <= 0:
            raise WorkflowError(f"timeout-minutes must be positive in job {key}")
        strategy = job.get("strategy", {})
        for matrix in expand_matrix(strategy):
            suffix = f" ({', '.join(str(value) for value in matrix.values())})" if matrix else ""
            result.append(
                ActionJob(
                    id=uuid.uuid4().hex,
                    key=key,
                    name=str(job.get("name", key)) + suffix,
                    needs=needs,
                    matrix=matrix,
                    timeout_seconds=min(max(1, int(duration * 60)), max_timeout),
                    continue_on_error=job.get("continue-on-error") is True,
                    steps=[
                        ActionStep(
                            id=str(step.get("id", index)),
                            name=str(step.get("name", step.get("uses", f"Run step {index + 1}"))),
                        )
                        for index, step in enumerate(job["steps"])
                    ],
                )
            )
        if len(result) > MAX_JOBS:
            raise WorkflowError("Workflow exceeds 256 expanded jobs")
    remaining = set(jobs)
    while remaining:
        ready = {key for key in remaining if not (set(dependencies[key]) & remaining)}
        if not ready:
            raise WorkflowError("Workflow dependency graph contains a cycle")
        remaining -= ready
    return result
