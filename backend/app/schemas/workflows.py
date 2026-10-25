"""Version-one compiler IR and sandbox manifest boundary contracts."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue
from pydantic.alias_generators import to_camel


class CompilerModel(BaseModel):
    """Keep Python field names independent of the shared JSON wire format."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="forbid")


class RunDefaults(CompilerModel):
    """Default shell settings preserved by the compiler."""

    shell: str | None = None
    working_directory: str | None = Field(default=None, alias="working-directory")


class WorkflowDefaults(CompilerModel):
    """Workflow or job run defaults."""

    run: RunDefaults | None = None


class CompiledStepBase(CompilerModel):
    """Validated execution fields common to shell and action steps."""

    id: str
    name: str | None = None
    condition: JsonValue = Field(default=None, alias="if")
    env: dict[str, JsonValue] | None = None
    continue_on_error: JsonValue = Field(default=None, alias="continue-on-error")
    timeout_minutes: JsonValue = Field(default=None, alias="timeout-minutes")


class CompiledRunStep(CompiledStepBase):
    """A shell step whose expressions are evaluated by the job agent."""

    kind: Literal["run"]
    run: str
    shell: str | None = None
    working_directory: str | None = Field(default=None, alias="working-directory")


class CompiledActionStep(CompiledStepBase):
    """A prepared JavaScript or composite action invocation."""

    kind: Literal["action"]
    uses: str
    inputs: dict[str, JsonValue] | None = Field(default=None, alias="with")


type CompiledStep = Annotated[CompiledRunStep | CompiledActionStep, Field(discriminator="kind")]


class JobConfiguration(CompilerModel):
    """Execution configuration extracted from validated source tokens."""

    condition: JsonValue = Field(default=None, alias="if")
    env: dict[str, JsonValue] | None = None
    defaults: WorkflowDefaults | None = None
    outputs: dict[str, JsonValue] | None = None
    timeout_minutes: JsonValue = Field(default=None, alias="timeout-minutes")
    continue_on_error: JsonValue = Field(default=None, alias="continue-on-error")
    steps: list[CompiledStep] = Field(min_length=1)


class CompiledJob(CompilerModel):
    """One statically expanded variant, before sandbox resource assignment."""

    id: str = Field(min_length=1)
    key: str = Field(min_length=1)
    name: str
    needs: list[str]
    matrix: dict[str, JsonValue]
    strategy: dict[str, JsonValue]
    timeout_seconds: int = Field(gt=0)
    continue_on_error: bool
    config: JobConfiguration


class WorkflowContext(CompilerModel):
    """Workflow-level configuration shared by job manifests."""

    name: str
    env: dict[str, JsonValue] | None = None
    defaults: WorkflowDefaults | None = None


class CompiledWorkflow(CompilerModel):
    """The compiler's immutable, versioned, JSON-serializable result."""

    version: Literal[1]
    matched: bool
    workflow_name: str
    dispatch: bool
    env: dict[str, JsonValue] | None = None
    defaults: WorkflowDefaults | None = None
    inputs: dict[str, JsonValue]
    jobs: list[CompiledJob] = Field(max_length=256)


class CompileEvent(CompilerModel):
    """Authorized event context required for compiler-side trigger matching."""

    name: Literal["push", "pull_request", "workflow_dispatch"]
    ref: str
    action: str | None = None
    base_ref: str | None = None
    changed_paths: list[str] = Field(default_factory=list)
    repository: str | None = None
    inputs: dict[str, JsonValue] | None = None


class CompileRequest(CompilerModel):
    """Bounded source request sent to the on-demand compiler Function."""

    version: Literal[1] = 1
    filename: str
    source: str
    event: CompileEvent


class JobDependency(BaseModel):
    """Combined result and outputs of a job's matrix variants."""

    result: str
    outputs: dict[str, str]


class JobInput(BaseModel):
    """Versioned manifest consumed directly by the sandbox agent."""

    version: Literal[1] = 1
    workflow: WorkflowContext
    job: CompiledJob
    inputs: dict[str, JsonValue]
    timeout_seconds: int
    needs: dict[str, JobDependency]
    event_name: str
    event: dict[str, JsonValue]
    actor: str
    env: dict[str, str]
    secrets: dict[str, str]
    restore_url: str
    complete_url: str


class CompilerIssue(BaseModel):
    """A compiler diagnostic with optional source location."""

    filename: str | None = None
    message: str
    line: int | None = None
    column: int | None = None
    path: list[str | int] | None = None


class CompilerFailure(BaseModel):
    """Only structured validation failures become public workflow errors."""

    error: Literal["invalid_workflow", "invalid_request", "invalid_json"]
    issues: list[CompilerIssue] = Field(min_length=1, max_length=100)
