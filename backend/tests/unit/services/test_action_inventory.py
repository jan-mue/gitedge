import re
from pathlib import Path


def test_every_repository_action_has_an_integration_workflow_and_is_prepared() -> None:
    root = Path(__file__).resolve().parents[4]
    references = set()
    for workflow in (root / ".github/workflows").glob("*.yaml"):
        references.update(re.findall(r"uses:\s*([^\s#]+)", workflow.read_text()))
    examples = set()
    for workflow in (root / "backend/tests/integration/actions/workflows").glob("*.yaml"):
        examples.update(re.findall(r"uses:\s*([^\s#]+)", workflow.read_text()))
    prepared = set((root / "backend/actions-runtime/actions.txt").read_text().splitlines())
    assert references <= examples
    assert references <= prepared
