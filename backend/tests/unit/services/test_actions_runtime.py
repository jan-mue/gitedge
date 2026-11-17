import json

from app.schemas.actions import ActionJob, ActionStatus, ActionStep
from app.services.actions.runtime import MAX_LOG_BYTES, TRUNCATION_MARKER, finish_job, update_logs


def test_structured_logs_keep_untrusted_text_plain_and_redact_secrets() -> None:
    job = ActionJob(id="variant", key="test", name="test", steps=[ActionStep(id="hello", name="Hello")])
    records = [
        {"msg": "<script>alert('secret-value')</script>", "stepID": ["hello"], "raw_output": True},
        {"msg": "done", "stepID": ["hello"], "stepResult": "success"},
    ]
    update_logs(job, "\n".join(json.dumps(record) for record in records).encode(), {"TOKEN": "secret-value"})
    assert "secret-value" not in job.log
    assert "<script>alert('***')</script>" in job.steps[0].log
    assert job.steps[0].status == ActionStatus.SUCCESS


def test_large_logs_keep_masked_head_and_tail_with_a_shared_step_budget() -> None:
    job = ActionJob(
        id="variant",
        key="test",
        name="test",
        steps=[ActionStep(id="first", name="First"), ActionStep(id="last", name="Last")],
    )
    message = "head secret-value " + "é" * MAX_LOG_BYTES + " tail secret-value"
    records = [{"msg": message, "stepID": [step.id], "stepResult": "success"} for step in job.steps]
    update_logs(job, "\n".join(json.dumps(record) for record in records).encode(), {"TOKEN": "secret-value"})
    assert len(job.log.encode()) <= MAX_LOG_BYTES
    assert sum(len(step.log.encode()) for step in job.steps) <= MAX_LOG_BYTES
    for value in [job.log, *(step.log for step in job.steps)]:
        assert value.startswith("head *** ")
        assert value.rstrip().endswith(" tail ***")
        assert TRUNCATION_MARKER in value
        assert "secret-value" not in value
        assert "�" not in value
    assert all(step.status == ActionStatus.SUCCESS for step in job.steps)


def test_log_truncation_does_not_hide_late_step_results_or_split_secrets() -> None:
    job = ActionJob(id="variant", key="test", name="test", steps=[ActionStep(id="hello", name="Hello")])
    records = [
        {"msg": "secret-value" * MAX_LOG_BYTES, "stepID": ["hello"]},
        {"msg": "finished", "stepID": ["hello"], "stepResult": "failure"},
    ]
    update_logs(job, "\n".join(json.dumps(record) for record in records).encode(), {"TOKEN": "secret-value"})
    assert job.steps[0].status == ActionStatus.FAILURE
    assert job.log.endswith("finished")
    assert "secret" not in job.log
    assert len(job.log.encode()) <= MAX_LOG_BYTES


def test_missing_executor_result_fails_instead_of_becoming_success() -> None:
    job = ActionJob(id="variant", key="test", name="test")
    finish_job(job, {"exit-code": b"0"}, {})
    assert job.status == ActionStatus.FAILURE
    assert job.error is not None
    assert "without a job result" in job.error


def test_failed_state_export_overrides_successful_executor_result() -> None:
    job = ActionJob(id="variant", key="test", name="test")
    finish_job(job, {"result.json": b'{"status":"success"}', "exit-code": b"2"}, {})
    assert job.status == ActionStatus.FAILURE
    assert job.error == "Job bootstrap exited unsuccessfully"


def test_executor_result_without_bootstrap_completion_fails() -> None:
    job = ActionJob(id="variant", key="test", name="test")
    finish_job(job, {"result.json": b'{"status":"success"}'}, {})
    assert job.status == ActionStatus.FAILURE
    assert job.error == "Sandbox exited without a completion marker"


def test_timeout_is_failure_even_when_the_executor_reports_signal_cancellation() -> None:
    job = ActionJob(id="variant", key="test", name="test")
    finish_job(job, {"result.json": b'{"status":"cancelled"}', "exit-code": b"124"}, {})
    assert job.status == ActionStatus.FAILURE
    assert job.error == "Job exceeded timeout-minutes"
