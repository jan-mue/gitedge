"""Build executor inputs and turn its structured output into public job state."""

import json
from datetime import UTC, datetime
from typing import Any

from app.schemas.actions import ActionJob, ActionStatus


def redact(value: str, secrets: dict[str, str]) -> str:
    """Keep configured secrets out of persisted errors and logs, including SDK failures."""
    for secret in sorted(secrets.values(), key=len, reverse=True):
        if secret:
            value = value.replace(secret, "***")
    return value


def update_logs(job: ActionJob, data: bytes, secrets: dict[str, str]) -> None:
    """Group executor JSON records by step while preserving plain text safely."""
    lines: list[str] = []
    for step in job.steps:
        step.log = ""
    by_id = {step.id: step for step in job.steps}
    for raw in data.decode("utf-8", errors="replace").splitlines():
        try:
            entry: dict[str, Any] = json.loads(raw)
        except json.JSONDecodeError:
            lines.append(raw)
            continue
        if not isinstance(entry, dict):
            continue
        message = str(entry.get("msg", ""))
        lines.append(message)
        step_ids = entry.get("stepID", entry.get("stepid", []))
        step_id = str(step_ids[0]) if isinstance(step_ids, list) and step_ids else str(step_ids)
        step = by_id.get(step_id)
        if step is not None:
            step.log += redact(message, secrets) + "\n"
            status = entry.get("stepResult")
            if status in {"success", "failure", "skipped", "cancelled"}:
                step.status = ActionStatus(status)
            elif step.status == ActionStatus.QUEUED:
                step.status = ActionStatus.RUNNING
    job.log = redact("\n".join(lines), secrets)


def finish_job(job: ActionJob, files: dict[str, bytes], secrets: dict[str, str]) -> None:
    """Use explicit completion markers; missing/invalid results always fail the job."""
    job.completed_at = datetime.now(UTC)
    job.status = ActionStatus.FAILURE
    if "result.json" not in files:
        job.error = "Sandbox exited without a job result"
        return
    if "exit-code" not in files:
        job.error = "Sandbox exited without a completion marker"
        return
    try:
        result = json.loads(files["result.json"])
        status = ActionStatus(result["status"])
        if status not in {ActionStatus.SUCCESS, ActionStatus.FAILURE, ActionStatus.SKIPPED, ActionStatus.CANCELLED}:
            raise ValueError("Nonterminal job result")
        job.status = status
        job.error = redact(str(result["error"]), secrets) if result.get("error") else None
        if files["exit-code"].strip() == b"124":
            job.status = ActionStatus.FAILURE
            job.error = "Job exceeded timeout-minutes"
        elif files["exit-code"].strip() != b"0" and status != ActionStatus.FAILURE:
            job.status = ActionStatus.FAILURE
            job.error = "Job bootstrap exited unsuccessfully"
        job.outputs = {str(key): redact(str(value), secrets) for key, value in (result.get("outputs") or {}).items()}
        for step in job.steps:
            step_result = (result.get("steps") or {}).get(step.id)
            if step_result:
                conclusion = step_result.get("Conclusion", step_result.get("conclusion", "success"))
                step.status = ActionStatus(conclusion)
            elif step.status == ActionStatus.QUEUED:
                step.status = ActionStatus.SKIPPED
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        job.status = ActionStatus.FAILURE
        job.error = f"Invalid executor result: {exc}"
