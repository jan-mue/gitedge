from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from app.api.dependencies import get_actions_store
from app.config import settings
from app.entities.actions import WorkflowAttempt, WorkflowRun
from app.index import app
from app.schemas.actions import ActionJob, ActionStep
from app.services.actions.capabilities import issue_capability

if TYPE_CHECKING:
    from fastapi.testclient import TestClient

    from tests.unit.utils.fakes import FakeStores

OWNER = settings.FIRST_SUPERUSER.split("@")[0]


async def setup(client: TestClient, fakes: FakeStores) -> tuple[WorkflowRun, WorkflowAttempt, str]:
    client.post(f"{settings.API_V1_STR}/repositories/", json={"owner": OWNER, "name": "log-repo"}).raise_for_status()
    repo = await fakes.repository.get_by_owner_and_name(OWNER, "log-repo")
    repo.is_private = True
    store = app.dependency_overrides[get_actions_store]()
    attempt_id, run_id = uuid.uuid4(), uuid.uuid4()
    job = ActionJob(
        id=uuid.uuid4().hex,
        attempt_id=attempt_id,
        key="test",
        name="Test",
        status="running",
        steps=[ActionStep(id="hello", name="Hello")],
    )
    attempt = WorkflowAttempt(
        id=attempt_id, run_id=run_id, job_id=job.id, generation=1, fence=uuid.uuid4(), status="running", log_seq=0
    )
    run = WorkflowRun(
        id=run_id,
        repo_id=repo.id,
        jobs=[job.model_dump(mode="json")],
        name="CI",
        workflow=".gitedge/workflow/ci.yaml",
        status="running",
        sha="a" * 40,
        ref="refs/heads/main",
        actor=OWNER,
        event_name="push",
        created_at=datetime.now(UTC),
    )
    store.runs[run_id], store.attempts[attempt_id] = run, attempt
    return run, attempt, issue_capability(run, job, attempt, "actions:report")


def body(attempt: WorkflowAttempt) -> dict:
    return {
        "version": 1,
        "id": str(attempt.id),
        "job_id": attempt.job_id,
        "generation": attempt.generation,
        "fence": str(attempt.fence),
        "from_seq": 1,
        "to_seq": 2,
        "records": [{"seq": 1, "msg": "first", "step_id": "hello"}, {"seq": 2, "msg": "second", "step_id": "hello"}],
    }


async def test_private_history_sse_and_download_use_normal_repository_authorization(
    client: TestClient,
    fake_stores: FakeStores,
    superuser_token_headers: dict[str, str],
    normal_user_token_headers: dict[str, str],
) -> None:
    run, attempt, token = await setup(client, fake_stores)
    callback = f"{settings.API_V1_STR}/actions/attempts/{attempt.id}/logs"
    assert client.post(callback, json=body(attempt), headers={"Authorization": f"Bearer {token}"}).json() == {
        "acked_seq": 2
    }
    attempt.status = "success"
    fake_stores.redis.streams.clear()
    base = f"{settings.API_V1_STR}/repositories/{OWNER}/log-repo/actions/runs/{run.id}/attempts/{attempt.id}/logs"
    for path in [base, base + "/events", base + "/download"]:
        assert client.get(path).status_code == 404
        assert client.get(path, headers=normal_user_token_headers).status_code == 404
    history = client.get(base, headers=superuser_token_headers)
    assert "no-store" in history.headers["Cache-Control"]
    assert history.json()["next_seq"] == 2
    stream = client.get(base + "/events", headers={**superuser_token_headers, "Last-Event-ID": "1"})
    assert stream.status_code == 200
    assert "text/event-stream" in stream.headers["Content-Type"]
    assert "id: 1\n" not in stream.text
    assert "id: 2\n" in stream.text
    assert "event: end" in stream.text
    assert "no-store" in stream.headers["Cache-Control"]
    assert client.get(base + "/download", headers=superuser_token_headers).text == "first\nsecond\n"
    wrong = base.replace(str(run.id), str(uuid.uuid4()))
    assert client.get(wrong, headers=superuser_token_headers).status_code == 404


async def test_uploads_require_current_capabilities_and_bounded_bodies(
    client: TestClient, fake_stores: FakeStores
) -> None:
    _, attempt, token = await setup(client, fake_stores)
    path = f"{settings.API_V1_STR}/actions/attempts/{attempt.id}/logs"
    assert client.post(path, json=body(attempt)).status_code == 403
    assert client.post(path, params={"token": token}, json=body(attempt)).status_code == 403
    headers = {"Authorization": f"Bearer {token}"}
    assert client.post(path, headers=headers, content=b"invalid").status_code == 422
    assert client.post(path, headers=headers, content=b"x" * (256 * 1024 + 1)).status_code == 413
    assert (
        client.post(path.replace(str(attempt.id), str(uuid.uuid4())), headers=headers, json=body(attempt)).status_code
        == 403
    )


async def test_result_callbacks_never_inspect_a_sandbox(client: TestClient, fake_stores: FakeStores) -> None:
    _, attempt, token = await setup(client, fake_stores)
    path = f"{settings.API_V1_STR}/actions/attempts/{attempt.id}/complete"
    payload = {key: value for key, value in body(attempt).items() if key not in {"records", "from_seq", "to_seq"}}
    payload.update(exit_code=0, last_seq=0, result={"status": "success", "steps": {}, "outputs": {"value": "ready"}})
    headers = {"Authorization": f"Bearer {token}"}
    assert client.post(path, headers=headers, json=payload).status_code == 202
    assert client.post(path, headers=headers, json=payload).status_code == 202
    assert attempt.status == "success"
    assert client.post(path, headers=headers, json={**payload, "generation": 2}).status_code == 403
