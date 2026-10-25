"""Real Docker jobs through Git HTTP, PostgreSQL, Redis, blob storage, and Actions APIs."""

from __future__ import annotations

import asyncio
import io
import json
import tarfile
import time
import uuid
import zipfile
from pathlib import Path
from typing import TYPE_CHECKING

import httpx2 as httpx
import psycopg
import pytest
from aiodocker import Docker

from app.clients.blob_storage import S3Client
from tests.conftest import FIRST_SUPERUSER, FIRST_SUPERUSER_PASSWORD
from tests.git import run_git

if TYPE_CHECKING:
    from collections.abc import Generator

    from qstash import QStash
    from testcontainers.core.container import DockerContainer
    from xprocess import XProcess


@pytest.fixture
def actions_repo(app_url: str, tmp_path: Path) -> Generator[tuple[httpx.Client, Path, str]]:
    with httpx.Client(base_url=app_url, timeout=180) as client:
        login = client.post(
            "/api/v1/login/access-token", data={"username": FIRST_SUPERUSER, "password": FIRST_SUPERUSER_PASSWORD}
        )
        login.raise_for_status()
        token = login.json()["access_token"]
        client.headers["Authorization"] = f"Bearer {token}"
        source = tmp_path / "source"
        source.mkdir()
        run_git(source, ["init", "-b", "main"])
        run_git(source, ["config", "user.email", "test@example.com"])
        run_git(source, ["config", "user.name", "Test User"])
        run_git(source, ["config", "http.extraHeader", f"Authorization: Bearer {token}"])
        workflows = source / ".gitedge/workflow"
        workflows.mkdir(parents=True)
        for fixture in (Path(__file__).parent / "workflows").glob("*.yaml"):
            if fixture.name == "smoke.yaml":
                shared = source / ".github/workflows/smoke.yaml"
                shared.parent.mkdir(parents=True, exist_ok=True)
                shared.write_text(fixture.read_text())
                (workflows / fixture.name).symlink_to("../../.github/workflows/smoke.yaml")
            else:
                (workflows / fixture.name).write_text(fixture.read_text())
        (source / "README.md").write_text("# Actions fixture\n")
        (source / "example.py").write_text('print("hello actions")\n')
        (source / ".pre-commit-config.yaml").write_text("repos: []\n")
        run_git(source, ["add", "."])
        run_git(source, ["commit", "-m", "Add Actions examples"])
        run_git(source, ["remote", "add", "origin", f"{app_url}/admin/actions-fixture.git"])
        run_git(source, ["push", "origin", "main"])
        path = "/api/v1/repositories/admin/actions-fixture/actions"
        yield client, source, path
        response = client.get(f"{path}/runs")
        response.raise_for_status()
        for run in response.json():
            client.post(f"{path}/runs/{run['id']}/cancel")


def wait_for_run(client: httpx.Client, path: str, run_id: str | None = None, seconds: int = 180) -> dict:
    deadline = time.monotonic() + seconds
    last = []
    while time.monotonic() < deadline:
        response = client.get(f"{path}/runs")
        response.raise_for_status()
        last = response.json()
        selected = next((run for run in last if run_id is None or run["id"] == run_id), None)
        if (
            selected
            and selected["status"] not in {"queued", "running"}
            and all(job["sandbox"] is None for job in selected["jobs"])
        ):
            return selected
        time.sleep(0.25)
    pytest.fail(f"Workflow did not finish: {json.dumps(last, indent=2)}")


def wait_for_started_job(client: httpx.Client, path: str, run_id: str) -> dict:
    deadline = time.monotonic() + 180
    while time.monotonic() < deadline:
        response = client.get(f"{path}/runs")
        response.raise_for_status()
        run = next(run for run in response.json() if run["id"] == run_id)
        if "Long job started" in run["jobs"][0]["log"]:
            return run["jobs"][0]
        time.sleep(0.25)
    pytest.fail("The job did not start in Docker through QStash")


def wait_for_access(log_file: Path, offset: int, operation: str, status: int, count: int = 1) -> None:
    deadline = time.monotonic() + 20
    expected = f'POST /api/v1/actions/internal/{operation} HTTP/1.1" {status}'
    while time.monotonic() < deadline:
        if log_file.read_bytes()[offset:].decode(errors="replace").count(expected) >= count:
            return
        time.sleep(0.1)
    pytest.fail(f"QStash did not deliver {count} {operation} callbacks returning HTTP {status}")


def test_push_runs_matrix_jobs_in_separate_sandboxes(
    actions_repo: tuple[httpx.Client, Path, str], infrastructure: dict[str, str]
) -> None:
    client, _, path = actions_repo
    # Observe persistence without polling the Actions API: sandbox completion
    # callbacks must advance the entire DAG, including the dependent job.
    deadline = time.monotonic() + 180
    db_url = infrastructure["DATABASE_URL"].replace("postgresql+psycopg://", "postgresql://")
    with psycopg.connect(db_url, autocommit=True) as connection:
        while time.monotonic() < deadline:
            row = connection.execute("SELECT status FROM workflow_run ORDER BY created_at DESC LIMIT 1").fetchone()
            if row and row[0] not in {"queued", "running"}:
                break
            time.sleep(0.25)
        else:
            pytest.fail("Completion callbacks did not advance the workflow without API polling")
    run = wait_for_run(client, path)
    assert run["status"] == "success", json.dumps(run, indent=2)
    assert len(run["jobs"]) == 3
    assert all(job["status"] == "success" for job in run["jobs"])
    assert all(job["sandbox"] is None for job in run["jobs"])
    assert "Dependency outputs verified" in run["jobs"][-1]["log"]

    async def has_remaining_jobs() -> bool:
        async with Docker() as client:
            return bool(await client.containers.list(all=True, filters={"label": ["gitedge.actions=true"]}))

    assert not asyncio.run(has_remaining_jobs())


def test_failed_jobs_skip_dependents_but_run_always_cleanup(actions_repo: tuple[httpx.Client, Path, str]) -> None:
    client, _, path = actions_repo
    wait_for_run(client, path)
    dispatch = client.post(f"{path}/dispatch", json={"workflow": ".gitedge/workflow/failure.yaml"})
    dispatch.raise_for_status()
    run = wait_for_run(client, path, dispatch.json()["id"])
    assert run["status"] == "failure", json.dumps(run, indent=2)
    assert [job["status"] for job in run["jobs"]] == ["failure", "skipped", "success"]
    assert "Cleanup ran" in run["jobs"][0]["log"]
    assert "Failure reported" in run["jobs"][2]["log"]


def test_tooling_actions_cache_and_artifacts(
    actions_repo: tuple[httpx.Client, Path, str], infrastructure: dict[str, str]
) -> None:
    client, _, path = actions_repo
    wait_for_run(client, path)

    async def artifact_state(run_id: str) -> bytes | None:
        blobs = S3Client(
            endpoint=infrastructure["S3_ENDPOINT"],
            access_key=infrastructure["S3_ACCESS_KEY"],
            secret_key=infrastructure["S3_SECRET_KEY"],
            bucket=infrastructure["S3_BUCKET"],
        )
        keys = await blobs.list_keys("actions/")
        key = next(key for key in keys if f"/{run_id}/attempts/" in key and key.endswith("/state.tar.gz"))
        caches = [key for key in keys if "/cache/" in key]
        assert caches, "Workflow cache archives must be persisted in S3"
        for cache_key in caches:
            assert await blobs.get(cache_key)
        return await blobs.get(key)

    for iteration in range(2):
        if iteration:
            bystander = client.post(f"{path}/dispatch", json={"workflow": ".gitedge/workflow/cache-bystander.yaml"})
            bystander.raise_for_status()
            assert wait_for_run(client, path, bystander.json()["id"])["status"] == "success"
        dispatch = client.post(f"{path}/dispatch", json={"workflow": ".gitedge/workflow/tooling.yaml"})
        dispatch.raise_for_status()
        run = wait_for_run(client, path, dispatch.json()["id"], seconds=600)
        assert run["status"] == "success", json.dumps(run, indent=2)
        for step in run["jobs"][0]["steps"]:
            expected = "skipped" if step["name"] == "Verify restored cache" and not iteration else "success"
            assert step["status"] == expected, json.dumps({"iteration": iteration, "run": run}, indent=2)
        state = asyncio.run(artifact_state(run["id"]))
        assert state is not None
        with tarfile.open(fileobj=io.BytesIO(state), mode="r:gz") as archive:
            member = next(member for member in archive if member.name.endswith("/example-results.zip"))
            uploaded = archive.extractfile(member)
            assert uploaded is not None
            with zipfile.ZipFile(io.BytesIO(uploaded.read())) as artifact:
                assert artifact.read("result.txt") == b"artifact contents\n"
        if iteration:
            assert "Portable cache restored" in run["jobs"][0]["log"]
            assert "uv cache restored" in run["jobs"][0]["log"]


def test_codeql_init_and_analyze_use_prepared_tools(actions_repo: tuple[httpx.Client, Path, str]) -> None:
    client, _, path = actions_repo
    wait_for_run(client, path)
    dispatch = client.post(f"{path}/dispatch", json={"workflow": ".gitedge/workflow/codeql.yaml"})
    dispatch.raise_for_status()
    run = wait_for_run(client, path, dispatch.json()["id"], seconds=600)
    assert run["status"] == "success", json.dumps(run, indent=2)
    assert "Verify SARIF results" in run["jobs"][0]["log"]


def test_cancellation_destroys_running_jobs_and_skips_queued_jobs(actions_repo: tuple[httpx.Client, Path, str]) -> None:
    client, _, path = actions_repo
    wait_for_run(client, path)
    dispatch = client.post(f"{path}/dispatch", json={"workflow": ".gitedge/workflow/cancellation.yaml"})
    dispatch.raise_for_status()
    run_id = dispatch.json()["id"]
    job = wait_for_started_job(client, path, run_id)

    async def completion_url() -> str:
        async with Docker() as docker:
            container = await docker.containers.get(job["sandbox"])
            configuration = await container.show()
            descriptor = next(
                value.removeprefix("GITEDGE_JOB=")
                for value in configuration["Config"]["Env"]
                if value.startswith("GITEDGE_JOB=")
            )
            return json.loads(descriptor)["complete_url"]

    stale_url = asyncio.run(completion_url())
    response = client.post(f"{path}/runs/{run_id}/cancel")
    response.raise_for_status()
    run = wait_for_run(client, path, run_id)
    assert run["status"] == "cancelled"
    assert all(job["status"] == "cancelled" and job["sandbox"] is None for job in run["jobs"])
    stale_path = stale_url.split("/api/v1/", 1)[1]
    assert client.post(f"/api/v1/{stale_path}").status_code == 403


def test_timeout_completes_without_actions_api_polling(
    actions_repo: tuple[httpx.Client, Path, str], infrastructure: dict[str, str]
) -> None:
    client, _, path = actions_repo
    wait_for_run(client, path)
    response = client.post(f"{path}/dispatch", json={"workflow": ".gitedge/workflow/timeout.yaml"})
    response.raise_for_status()
    run_id = response.json()["id"]
    db_url = infrastructure["DATABASE_URL"].replace("postgresql+psycopg://", "postgresql://")
    deadline = time.monotonic() + 60
    with psycopg.connect(db_url, autocommit=True) as connection:
        while time.monotonic() < deadline:
            row = connection.execute("SELECT status FROM workflow_run WHERE id = %s", (run_id,)).fetchone()
            if row and row[0] == "failure":
                break
            time.sleep(0.25)
        else:
            pytest.fail("Timed-out sandbox did not notify the controller without API polling")
    run = wait_for_run(client, path, run_id)
    assert run["status"] == "failure", json.dumps(run, indent=2)
    assert run["jobs"][0]["error"] == "Job exceeded timeout-minutes"
    assert run["jobs"][0]["sandbox"] is None


def test_invalid_parser_input_never_creates_a_sandbox(actions_repo: tuple[httpx.Client, Path, str]) -> None:
    client, source, path = actions_repo
    wait_for_run(client, path)
    (source / ".gitedge/workflow/smoke.yaml").unlink()
    (source / ".gitedge/workflow/invalid.yaml").write_text(
        "on: push\njobs:\n  invalid:\n    steps:\n      - run: true\n"
    )
    run_git(source, ["add", "."])
    run_git(source, ["commit", "-m", "Reject invalid workflow before provisioning"])
    run_git(source, ["push", "origin", "main"])
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        runs = client.get(f"{path}/runs")
        runs.raise_for_status()
        invalid = next((run for run in runs.json() if run["workflow"] == ".gitedge/workflow/invalid.yaml"), None)
        if invalid:
            break
        time.sleep(0.1)
    else:
        pytest.fail("The pushed invalid workflow was not recorded")
    assert invalid["status"] == "failure"
    assert invalid["jobs"] == []
    assert "runs-on" in invalid["error"]

    async def remaining_jobs() -> bool:
        async with Docker() as docker:
            return bool(await docker.containers.list(all=True, filters={"label": ["gitedge.actions=true"]}))

    assert not asyncio.run(remaining_jobs())


def test_real_qstash_retries_a_failed_signed_callback(
    actions_repo: tuple[httpx.Client, Path, str],
    infrastructure: dict[str, str],
    backend_url: str,
    xprocess: XProcess,
    qstash: QStash,
) -> None:
    backend_log_file = Path(str(xprocess.getinfo("backend").logpath))
    client, _, path = actions_repo
    wait_for_run(client, path)
    response = client.post(f"{path}/dispatch", json={"workflow": ".gitedge/workflow/cancellation.yaml"})
    response.raise_for_status()
    run_id = response.json()["id"]
    wait_for_started_job(client, path, run_id)
    db_url = infrastructure["DATABASE_URL"].replace("postgresql+psycopg://", "postgresql://")
    with psycopg.connect(db_url) as connection:
        connection.execute("SELECT id FROM workflow_run WHERE id = %s FOR UPDATE", (run_id,))
        message = connection.execute(
            "SELECT id FROM workflow_outbox WHERE run_id = %s AND kind = 'inspect' "
            "AND acknowledged_at IS NULL ORDER BY due_at DESC LIMIT 1",
            (run_id,),
        ).fetchone()
        assert message is not None
        offset = backend_log_file.stat().st_size
        qstash.message.publish_json(
            url=f"{backend_url.replace('127.0.0.1', 'host.docker.internal')}/api/v1/actions/internal/inspect",
            body={"version": 1, "id": str(message[0])},
            deduplication_id=str(uuid.uuid4()),
            retries=5,
            retry_delay="1000",
        )
        wait_for_access(backend_log_file, offset, "inspect", 503)
    with psycopg.connect(db_url, autocommit=True) as connection:
        connection.execute(
            "UPDATE workflow_attempt SET claim = NULL, lease_until = NULL WHERE run_id = %s AND status = 'running'",
            (run_id,),
        )
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            row = connection.execute(
                "SELECT acknowledged_at FROM workflow_outbox WHERE id = %s", (message[0],)
            ).fetchone()
            if row and row[0] is not None:
                break
            time.sleep(0.1)
        else:
            pytest.fail("QStash did not retry the command after the database lock was released")
    client.post(f"{path}/runs/{run_id}/cancel").raise_for_status()
    assert wait_for_run(client, path, run_id)["status"] == "cancelled"


def test_committed_outbox_recovers_after_real_publish_failure(
    actions_repo: tuple[httpx.Client, Path, str],
    infrastructure: dict[str, str],
    qstash_container: DockerContainer,
) -> None:
    client, _, path = actions_repo
    initial = wait_for_run(client, path)
    broker = qstash_container.get_wrapped_container()
    broker.pause()
    try:
        response = client.post(f"{path}/dispatch", json={"workflow": ".gitedge/workflow/cache-bystander.yaml"})
        assert response.status_code == 503
    finally:
        broker.unpause()
    response = client.get(f"{path}/runs")
    response.raise_for_status()
    run_id = next(run["id"] for run in response.json() if run["id"] != initial["id"])
    run = wait_for_run(client, path, run_id)
    assert run["status"] == "success", json.dumps(run, indent=2)
    db_url = infrastructure["DATABASE_URL"].replace("postgresql+psycopg://", "postgresql://")
    with psycopg.connect(db_url) as connection:
        row = connection.execute(
            "SELECT bool_and(published_at IS NOT NULL AND acknowledged_at IS NOT NULL) "
            "FROM workflow_outbox WHERE run_id = %s AND kind = 'dispatch'",
            (run_id,),
        ).fetchone()
    assert row == (True,)


def test_real_duplicate_deliveries_do_not_create_another_attempt(
    actions_repo: tuple[httpx.Client, Path, str],
    infrastructure: dict[str, str],
    backend_url: str,
    xprocess: XProcess,
    qstash: QStash,
) -> None:
    backend_log_file = Path(str(xprocess.getinfo("backend").logpath))
    client, _, path = actions_repo
    run = wait_for_run(client, path)
    offset = backend_log_file.stat().st_size
    db_url = infrastructure["DATABASE_URL"].replace("postgresql+psycopg://", "postgresql://")
    with psycopg.connect(db_url, autocommit=True) as connection:
        message = connection.execute(
            "SELECT id FROM workflow_outbox WHERE run_id = %s AND kind = 'dispatch' LIMIT 1",
            (run["id"],),
        ).fetchone()
        assert message is not None
        count = connection.execute("SELECT count(*) FROM workflow_attempt WHERE run_id = %s", (run["id"],)).fetchone()
        destination = f"{backend_url.replace('127.0.0.1', 'host.docker.internal')}/api/v1/actions/internal/dispatch"
        for _ in range(2):
            qstash.message.publish_json(
                url=destination, body={"version": 1, "id": str(message[0])}, deduplication_id=str(uuid.uuid4())
            )
        wait_for_access(backend_log_file, offset, "dispatch", 202, count=2)
        assert (
            connection.execute("SELECT count(*) FROM workflow_attempt WHERE run_id = %s", (run["id"],)).fetchone()
            == count
        )


def test_internal_callbacks_require_a_valid_qstash_signature(app_url: str) -> None:
    for signature in ("", "forged-signature"):
        response = httpx.post(
            f"{app_url}/api/v1/actions/internal/dispatch",
            json={"version": 1, "id": str(uuid.uuid4())},
            headers={"Upstash-Signature": signature},
            timeout=10,
        )
        assert response.status_code == 403
