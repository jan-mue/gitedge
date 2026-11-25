from typing import TYPE_CHECKING

from pydantic_ai.models.test import TestModel
from vercel.sandbox import SandboxClient

from app.agents.dependencies import SetupAgentDeps
from app.agents.setup import run_setup_agent
from app.sandboxes.vercel import VercelSandbox

if TYPE_CHECKING:
    from pytest_mock import MockerFixture

    from tests.unit.utils.fakes import FakeStores


async def test_setup_run_supplies_a_setup_typed_agent_and_explicit_workspace(
    mocker: MockerFixture, fake_stores: FakeStores
) -> None:
    client = mocker.create_autospec(SandboxClient, instance=True)
    deps = SetupAgentDeps(streams=mocker.Mock(), blobs=fake_stores.blob, sandbox=VercelSandbox(client=client))
    workspace = mocker.Mock()
    runner = mocker.patch("app.agents.setup.run_agent", return_value=[])
    assert (
        await run_setup_agent(
            deps,
            workspace=workspace,
            run_id="setup-run",
            session_id="setup-session",
            prompt="Prepare the environment",
            model=TestModel(),
        )
        == []
    )
    assert runner.await_args is not None
    agent, supplied = runner.await_args.args
    assert agent.deps_type is SetupAgentDeps
    assert supplied is deps
    assert runner.await_args.kwargs["workspace"] is workspace
    client.get_or_create_sandbox.assert_not_awaited()
