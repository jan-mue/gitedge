from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from app.clients.sandboxes import AbstractSandboxClient, SandboxError
from app.entities.actions import WorkflowRun
from app.services.actions.service import ActionsService
from app.services.actions.workflows import plan_jobs
from tests.unit.utils.actions import FakeActionsStore

if TYPE_CHECKING:
    from pytest_mock import MockerFixture

    from tests.unit.utils.fakes import FakeStores


async def test_provisioning_failures_finish_out_of_order_dependencies_without_periodic_recovery(
    mocker: MockerFixture, fake_stores: FakeStores
) -> None:
    provider = mocker.AsyncMock(spec=AbstractSandboxClient)
    provider.start.side_effect = SandboxError("Prepared image is unavailable")
    store = FakeActionsStore()
    definition = {
        "jobs": {
            "dependent": {"needs": "parent", "steps": [{"run": "echo dependent"}]},
            "parent": {"steps": [{"run": "echo parent"}]},
        }
    }
    run = await store.add_run(
        WorkflowRun(
            id=uuid.uuid4(),
            repo_id=uuid.uuid4(),
            workflow=".gitedge/workflow/ci.yaml",
            definition="jobs: {}",
            event={"repository": {"full_name": "owner/repo"}},
            event_name="push",
            event_key="push-1",
            actor="owner",
            provider="docker",
            sha="a" * 40,
            ref="refs/heads/main",
            status="queued",
            jobs=[job.model_dump(mode="json") for job in plan_jobs(definition, 60)],
        )
    )
    service = ActionsService(
        store,
        mocker.Mock(),
        fake_stores.repository,
        fake_stores.blob,
        {"docker": provider},
        provider="docker",
        max_timeout=60,
        max_parallel=1,
    )
    assert await service.advance_run(run.repo_id, run.id)
    assert run.status == "failure"
    assert all(job["status"] == "failure" and job["sandbox"] is None for job in run.jobs)
    assert provider.start.await_count == 2
    assert provider.delete.await_count == 2
