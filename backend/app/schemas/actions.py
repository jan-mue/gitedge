"""Public workflow runs and sandbox-neutral job specifications."""

import uuid
from datetime import datetime
from enum import StrEnum

from pydantic import Field, JsonValue

from app.schemas.base import GitEdgeBaseModel


class ActionStatus(StrEnum):
    """Workflow and job lifecycle states."""

    QUEUED = "queued"
    RUNNING = "running"
    SUCCESS = "success"
    FAILURE = "failure"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"


class ActionStep(GitEdgeBaseModel):
    """One step and its masked, plain-text log."""

    id: str
    name: str
    status: ActionStatus = ActionStatus.QUEUED
    log: str = ""


class ActionJob(GitEdgeBaseModel):
    """A single matrix variant, always assigned its own sandbox."""

    id: str
    key: str
    compiled_id: str | None = None
    attempt_id: uuid.UUID | None = None
    name: str
    matrix: dict[str, JsonValue] = Field(default_factory=dict)
    needs: list[str] = Field(default_factory=list)
    status: ActionStatus = ActionStatus.QUEUED
    sandbox: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    timeout_seconds: int = 1200
    outputs: dict[str, str] = Field(default_factory=dict)
    steps: list[ActionStep] = Field(default_factory=list)
    log: str = ""
    error: str | None = None
    continue_on_error: bool = False


class ActionRun(GitEdgeBaseModel):
    """Persisted run history exposed to the Actions UI."""

    id: uuid.UUID
    workflow: str
    name: str
    sha: str
    ref: str
    actor: str
    event_name: str
    status: ActionStatus
    created_at: datetime
    completed_at: datetime | None = None
    jobs: list[ActionJob]
    error: str | None = None


class PullRequestChecks(GitEdgeBaseModel):
    """Latest workflow results for the current pull request head commit."""

    head_sha: str
    runs: list[ActionRun]


class WorkflowInfo(GitEdgeBaseModel):
    """A workflow discovered at a revision."""

    path: str
    name: str
    dispatch: bool = False


class WorkflowDispatch(GitEdgeBaseModel):
    """Dispatch a workflow version from an existing repository revision."""

    workflow: str = Field(pattern=r"^\.gitedge/workflow/[^/]+\.ya?ml$")
    ref: str = Field(default="HEAD", min_length=1, max_length=255)
    inputs: dict[str, str] = Field(default_factory=dict)
