"""Turn structured executor output into public job state."""

import io
import json
import tarfile
from datetime import UTC, datetime
from pathlib import PurePosixPath
from typing import Any

from app.exceptions import WorkflowError
from app.schemas.action_dispatch import AttemptIdentity
from app.schemas.actions import ActionJob, ActionStatus


def redact(value: str, secrets: dict[str, str]) -> str:
    """Keep configured secrets out of persisted errors and logs, including SDK failures."""
    for secret in sorted(secrets.values(), key=len, reverse=True):
        if secret:
            value = value.replace(secret, "***")
    return value


def update_logs(job: ActionJob, data: bytes, secrets: dict[str, str], identity: AttemptIdentity | None = None) -> None:
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
        if identity and (
            entry.get("attemptID") != str(identity.id)
            or entry.get("fence") != str(identity.fence)
            or entry.get("jobID") != identity.job_id
            or entry.get("generation") != identity.generation
        ):
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


def finish_job(
    job: ActionJob, files: dict[str, bytes], secrets: dict[str, str], identity: AttemptIdentity | None = None
) -> None:
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
        if identity and AttemptIdentity.model_validate(result.get("attempt")) != identity:
            raise ValueError("Executor result belongs to a different attempt")
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


def merge_artifacts(archives: list[bytes]) -> bytes:
    """Combine committed artifact files without restoring arbitrary paths."""
    files: dict[str, bytes] = {}
    total = 0
    for data in archives:
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as archive:
            for member in archive:
                path = PurePosixPath(member.name)
                if (
                    not member.isfile()
                    or path.is_absolute()
                    or ".." in path.parts
                    or not path.parts
                    or path.parts[0] != "artifacts"
                ):
                    continue
                total += member.size - len(files.get(member.name, b""))
                if total > 32 * 1024 * 1024:
                    raise WorkflowError("Artifacts exceed 32 MiB")
                stream = archive.extractfile(member)
                if stream:
                    files[member.name] = stream.read()
    result = io.BytesIO()
    with tarfile.open(fileobj=result, mode="w:gz") as archive:
        for name, data in files.items():
            member = tarfile.TarInfo(name)
            member.size = len(data)
            archive.addfile(member, io.BytesIO(data))
    return result.getvalue()
