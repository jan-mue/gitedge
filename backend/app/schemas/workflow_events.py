"""GitHub-compatible event payloads with an internal event discriminator."""

from typing import Annotated, Literal

from pydantic import BaseModel, Field, TypeAdapter


class EventActor(BaseModel):
    """Identity included in repository and sender contexts."""

    login: str
    name: str = ""
    type: Literal["User", "Organization"] = "User"


class EventRepository(BaseModel):
    """Repository metadata available to workflow expressions."""

    full_name: str
    name: str = ""
    default_branch: str = ""
    private: bool = False
    html_url: str = ""
    clone_url: str = ""
    owner: EventActor | None = None


class WorkflowEventBase(BaseModel):
    """Commit context shared by workflow triggers."""

    ref: str = ""
    after: str = ""
    repository: EventRepository | None = None
    sender: EventActor | None = None
    changed_paths: list[str] = Field(default_factory=list)


class PushEvent(WorkflowEventBase):
    """Changed ref and paths delivered by Git receive."""

    event_name: Literal["push"] = Field(default="push", exclude=True)
    before: str = "0" * 40


class PullRequestRef(BaseModel):
    """Branch and exact commit for one side of a pull request."""

    ref: str = ""
    sha: str = ""


class PullRequestContext(BaseModel):
    """Pull request identity and compared revisions."""

    number: int
    head: PullRequestRef = Field(default_factory=PullRequestRef)
    base: PullRequestRef = Field(default_factory=PullRequestRef)


class PullRequestEvent(WorkflowEventBase):
    """Pull request activity and its head/base context."""

    event_name: Literal["pull_request"] = Field(default="pull_request", exclude=True)
    action: str = "opened"
    number: int = 0
    pull_request: PullRequestContext


class DispatchEvent(WorkflowEventBase):
    """Explicit workflow invocation with user-supplied inputs."""

    event_name: Literal["workflow_dispatch"] = Field(default="workflow_dispatch", exclude=True)
    inputs: dict[str, str] = Field(default_factory=dict)


class ScheduleEvent(WorkflowEventBase):
    """A schedule event supplied by an external caller."""

    event_name: Literal["schedule"] = Field(default="schedule", exclude=True)
    schedule: str


type WorkflowEvent = Annotated[
    PushEvent | PullRequestEvent | DispatchEvent | ScheduleEvent, Field(discriminator="event_name")
]

workflow_event_adapter = TypeAdapter(WorkflowEvent)
