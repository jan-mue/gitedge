"""Real Docker jobs through Git HTTP, PostgreSQL, Redis, blob storage, and Actions APIs."""

from __future__ import annotations

import asyncio
import io
import json
import tarfile
import time
import zipfile
from pathlib import Path
from typing import TYPE_CHECKING

import httpx2 as httpx
import psycopg
import pytest
from aiodocker import Docker

from app.clients.blob_storage import S3Client
from app.constants import BACKEND_DIR
from app.schemas.workflows import CompiledWorkflow
from tests.conftest import FIRST_SUPERUSER, FIRST_SUPERUSER_PASSWORD
from tests.git import run_git

if TYPE_CHECKING:
    from collections.abc import Generator


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
        if selected and selected["status"] not in {"queued", "running"}:
            return selected
        time.sleep(0.25)
    pytest.fail(f"Workflow did not finish: {json.dumps(last, indent=2)}")


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
        key = next(key for key in keys if key.endswith(f"/{run_id}/state.tar.gz"))
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
    response = client.post(f"{path}/runs/{run_id}/cancel")
    response.raise_for_status()
    run = wait_for_run(client, path, run_id)
    assert run["status"] == "cancelled"
    assert all(job["status"] == "cancelled" and job["sandbox"] is None for job in run["jobs"])


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


def test_real_bun_compiler_http_contract(actions_compiler_url: str, infrastructure: dict[str, str]) -> None:
    fixtures = BACKEND_DIR.parent / "packages/actions-runner/src/compiler/fixtures"
    request = {
        "version": 1,
        "filename": ".gitedge/workflow/basic.yaml",
        "source": (fixtures / "basic.yaml").read_text(),
        "event": {"name": "push", "ref": "refs/heads/main"},
    }
    with httpx.Client(timeout=15) as client:
        assert client.post(actions_compiler_url, json=request).status_code == 401
        response = client.post(
            actions_compiler_url,
            json=request,
            headers={"Authorization": f"Bearer {infrastructure['ACTIONS_COMPILER_TOKEN']}"},
        )
        response.raise_for_status()
        assert CompiledWorkflow.model_validate(response.json()) == CompiledWorkflow.model_validate_json(
            (fixtures / "basic.json").read_text()
        )
        rejected = client.post(
            actions_compiler_url,
            json={**request, "source": "on: [push\n"},
            headers={"Authorization": f"Bearer {infrastructure['ACTIONS_COMPILER_TOKEN']}"},
        )
        assert rejected.status_code == 422
        assert rejected.json()["issues"][0]["filename"] == request["filename"]
        assert rejected.json()["issues"][0]["line"] > 0
