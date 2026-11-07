import json
import re
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.schemas.workflows import CompiledWorkflow
from app.services.actions.workflows import instantiate_jobs, workflow_paths
from tests.unit.utils.actions import compiled_fixture


def test_golden_manifest_preserves_agent_fields_without_parsing_yaml() -> None:
    compiled = compiled_fixture()
    step = compiled.jobs[0].config.steps[0]
    assert step.kind == "run"
    assert step.shell == "bash"
    assert step.working_directory == "."
    assert step.timeout_minutes == 1
    jobs = instantiate_jobs(compiled, 60)
    assert jobs[0].compiled_id == compiled.jobs[0].id
    assert jobs[0].timeout_seconds == 60
    assert [step.id for step in jobs[0].steps] == ["command", "checkout"]


def test_manifest_contract_rejects_incompatible_versions_and_unknown_fields() -> None:
    payload = compiled_fixture().model_dump(mode="json", by_alias=True, exclude_none=True)
    with pytest.raises(ValidationError):
        CompiledWorkflow.model_validate({**payload, "version": 3})
    with pytest.raises(ValidationError):
        CompiledWorkflow.model_validate({**payload, "futureLanguage": {}})
    assert (
        json.loads(CompiledWorkflow.model_validate(payload).model_dump_json(by_alias=True, exclude_none=True))
        == payload
    )


def test_workflow_discovery_only_selects_direct_yaml_children() -> None:
    assert workflow_paths(
        ["README.md", ".gitedge/workflow/ci.yaml", ".gitedge/workflow/nested/invalid.yaml", ".github/workflows/ci.yaml"]
    ) == [".gitedge/workflow/ci.yaml"]


def test_shared_workflow_actions_have_integration_coverage_and_are_prepared() -> None:
    root = Path(__file__).resolve().parents[4]
    references = set()
    github_only = {"codeql.yaml", "integration-tests.yaml"}
    for workflow in (root / ".github/workflows").glob("*.yaml"):
        if workflow.name in github_only:
            continue
        references.update(re.findall(r"uses:\s*([^\s#]+)", workflow.read_text()))
    examples = set()
    for workflow in (root / "backend/tests/integration/actions/workflows").glob("*.yaml"):
        examples.update(re.findall(r"uses:\s*([^\s#]+)", workflow.read_text()))
    prepared = set((root / "packages/actions-runner/actions.txt").read_text().splitlines())
    assert references <= examples
    assert references <= prepared
