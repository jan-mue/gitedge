import uuid

import pytest
from pydantic import ValidationError

from app.schemas.action_logs import JobCompletion, JobResult, StepResult
from app.schemas.actions import ActionJob, ActionStatus, ActionStep
from app.services.actions.runtime import finish_job, redact


def completion(status: str, code: int = 0) -> JobCompletion:
    return JobCompletion(
        id=uuid.uuid4(),
        job_id="job",
        generation=1,
        fence=uuid.uuid4(),
        exit_code=code,
        last_seq=0,
        result=JobResult.model_validate({"status": status}),
    )


def test_bootstrap_failure_overrides_successful_result() -> None:
    job = ActionJob(id="job", key="test", name="Test")
    finish_job(job, completion("success", 2), {})
    assert job.status == ActionStatus.FAILURE
    assert job.error == "Job bootstrap exited unsuccessfully"


def test_timeout_is_failure_even_after_signal_cancellation() -> None:
    job = ActionJob(id="job", key="test", name="Test")
    finish_job(job, completion("cancelled", 124), {})
    assert job.status == ActionStatus.FAILURE
    assert job.error == "Job exceeded timeout-minutes"


def test_completion_redacts_outputs_and_preserves_step_conclusions_without_logs() -> None:
    job = ActionJob(id="job", key="test", name="Test", steps=[ActionStep(id="hello", name="Hello")])
    report = completion("success")
    report.result.outputs = {"value": "secret-value"}
    report.result.steps = {"hello": StepResult(outcome="failure", conclusion="success", outputs={})}
    finish_job(job, report, {"TOKEN": "secret-value"})
    assert job.outputs == {"value": "***"}
    assert job.steps[0].status == "success"
    assert "log" not in job.model_dump()
    assert "log" not in job.steps[0].model_dump()


@pytest.mark.parametrize("payload", [{}, {"status": "running"}, {"status": "unknown"}])
def test_nonterminal_or_missing_result_cannot_be_accepted(payload: dict) -> None:
    with pytest.raises(ValidationError):
        JobResult.model_validate(payload)


def test_multiline_secrets_are_masked_when_output_arrives_on_separate_lines() -> None:
    secrets = {"KEY": "first-secret-line\nsecond-secret-line"}
    assert redact("first-secret-line", secrets) == "***"
    assert redact("second-secret-line", secrets) == "***"
    assert redact(secrets["KEY"], secrets) == "***"
