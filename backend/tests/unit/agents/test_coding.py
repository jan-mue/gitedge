import uuid
from typing import TYPE_CHECKING

from pydantic_ai.models.test import TestModel
from vercel.sandbox import SandboxClient

from app.agents.coding import run_coding_agent
from app.agents.dependencies import AgentForgeScope, CodingAgentDeps
from app.sandboxes.vercel import VercelSandbox

if TYPE_CHECKING:
    from pytest_mock import MockerFixture

    from tests.unit.utils.fakes import FakeStores


async def test_coding_run_supplies_a_coding_typed_agent_with_required_forge_scope(
    mocker: MockerFixture, fake_stores: FakeStores
) -> None:
    client = mocker.create_autospec(SandboxClient, instance=True)
    scope = AgentForgeScope(user_id=uuid.uuid4(), session_id=uuid.uuid4(), repository_ids=(uuid.uuid4(),))
    deps = CodingAgentDeps(
        streams=mocker.Mock(),
        blobs=fake_stores.blob,
        sandbox=VercelSandbox(client=client),
        forge=mocker.Mock(),
        forge_scope=scope,
    )
    workspace = mocker.Mock()
    runner = mocker.patch("app.agents.coding.run_agent", return_value=[])
    assert (
        await run_coding_agent(
            deps,
            workspace=workspace,
            run_id="coding-run",
            session_id="coding-session",
            prompt="Change the repository",
            model=TestModel(),
        )
        == []
    )
    assert runner.await_args is not None
    agent, supplied = runner.await_args.args
    assert agent.deps_type is CodingAgentDeps
    assert supplied is deps
    assert supplied.forge_scope is scope
    assert runner.await_args.kwargs["workspace"] is workspace
    client.get_or_create_sandbox.assert_not_awaited()
