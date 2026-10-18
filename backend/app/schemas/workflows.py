"""Validated workflow capabilities and trigger filters."""

from typing import Self

from pydantic import BaseModel, Field, FiniteFloat, JsonValue, field_validator, model_validator


class WorkflowStep(BaseModel):
    """A shell command or a prepared action reference."""

    id: str | None = None
    name: str | None = None
    run: str | None = None
    uses: str | None = None

    @model_validator(mode="after")
    def _validate_action(self) -> Self:
        if (self.run is None) == (self.uses is None):
            raise ValueError("Each step must define exactly one of run or uses")
        if self.uses and self.uses.startswith("docker://"):
            raise ValueError("Docker actions require nested Docker and are not supported")
        return self


class WorkflowJob(BaseModel):
    """Job options supported by isolated sandbox execution."""

    name: str | None = None
    needs: list[str] = Field(default_factory=list)
    steps: list[WorkflowStep] = Field(min_length=1)
    strategy: dict[str, JsonValue] = Field(default_factory=dict)
    timeout_minutes: FiniteFloat = Field(default=20, alias="timeout-minutes", gt=0)
    continue_on_error: bool | str = Field(default=False, alias="continue-on-error")
    uses: str | None = None
    container: JsonValue = None
    services: JsonValue = None

    @field_validator("needs", mode="before")
    @classmethod
    def _normalize_needs(cls, value: str | list[str]) -> list[str]:
        return [value] if isinstance(value, str) else value

    @model_validator(mode="after")
    def _validate_capabilities(self) -> Self:
        if self.uses or self.container or self.services:
            raise ValueError("Reusable workflows, job containers, and service containers are not supported")
        return self


class EventFilters(BaseModel):
    """GitHub event activity, ref, and path filters."""

    types: list[str] = Field(default_factory=list)
    branches: list[str] = Field(default_factory=list)
    branches_ignore: list[str] = Field(default_factory=list, alias="branches-ignore")
    tags: list[str] = Field(default_factory=list)
    tags_ignore: list[str] = Field(default_factory=list, alias="tags-ignore")
    paths: list[str] | None = None
    paths_ignore: list[str] | None = Field(default=None, alias="paths-ignore")


class JobDependency(BaseModel):
    """Combined result and outputs of a job's matrix variants."""

    result: str
    outputs: dict[str, str]


class JobInput(BaseModel):
    """Descriptor passed to the Bun runner without source files."""

    workflow: str
    job: str
    timeout_seconds: int
    matrix: dict[str, JsonValue]
    needs: dict[str, JobDependency]
    event_name: str
    event: dict[str, JsonValue]
    actor: str
    env: dict[str, str]
    secrets: dict[str, str]
    restore_url: str
    complete_url: str
    cache_url: str
