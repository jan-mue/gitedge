"""Turn structured executor output into public job state."""

import io
import tarfile
from datetime import UTC, datetime
from pathlib import PurePosixPath
from typing import TYPE_CHECKING

from app.exceptions import WorkflowError
from app.schemas.actions import ActionJob, ActionStatus

if TYPE_CHECKING:
    from app.schemas.action_logs import JobCompletion

TIMEOUT_EXIT_CODE = 124


def redact(value: str, secrets: dict[str, str]) -> str:
    """Keep configured secrets out of persisted errors and logs, including SDK failures."""
    masks = {part for secret in secrets.values() for part in (secret, *secret.splitlines()) if part}
    for secret in sorted(masks, key=len, reverse=True):
        value = value.replace(secret, "***")
    return value


def finish_job(job: ActionJob, completion: JobCompletion, secrets: dict[str, str]) -> None:
    """Apply the validated result pushed by the current agent."""
    result = completion.result
    job.completed_at = datetime.now(UTC)
    job.status = ActionStatus(result.status)
    job.error = redact(result.error, secrets) if result.error else None
    if completion.exit_code == TIMEOUT_EXIT_CODE:
        job.status, job.error = ActionStatus.FAILURE, "Job exceeded timeout-minutes"
    elif completion.exit_code != 0 and result.status != "failure":
        job.status, job.error = ActionStatus.FAILURE, "Job bootstrap exited unsuccessfully"
    job.outputs = {key: redact(value, secrets) for key, value in result.outputs.items()}
    for step in job.steps:
        status = result.steps.get(step.id)
        step.status = ActionStatus(status.conclusion) if status else ActionStatus.SKIPPED


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
