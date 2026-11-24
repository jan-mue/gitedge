import uuid
from typing import TYPE_CHECKING

from pydantic_ai import RunContext
from pydantic_ai.models.test import TestModel
from pydantic_ai.usage import RunUsage

from app.agents.dependencies import AgentForgeScope, CodingAgentDeps
from app.agents.forge import create_issue
from app.services.agent_forge import AgentForgeService

if TYPE_CHECKING:
    from pytest_mock import MockerFixture

    from tests.unit.utils.fakes import FakeStores


async def test_issue_tool_uses_required_coding_dependencies_directly(
    mocker: MockerFixture, fake_stores: FakeStores
) -> None:
    forge = mocker.create_autospec(AgentForgeService, instance=True)
    forge.create_issue.return_value = mocker.Mock(number=1, repo_owner="owner", repo_name="repo", title="Issue")
    scope = AgentForgeScope(user_id=uuid.uuid4(), session_id=uuid.uuid4(), repository_ids=(uuid.uuid4(),))
    deps = CodingAgentDeps(
        streams=mocker.Mock(), blobs=fake_stores.blob, sandbox=mocker.Mock(), forge=forge, forge_scope=scope
    )
    ctx = RunContext(deps=deps, model=TestModel(), usage=RunUsage(), tool_call_id="issue-call")
    assert await create_issue(ctx, "owner/repo", "Issue", "Details") == {
        "number": 1,
        "url": "/owner/repo/issues/1",
        "title": "Issue",
    }
    forge.create_issue.assert_awaited_once()
    assert forge.create_issue.await_args is not None
    supplied_scope, repository, body, call_id = forge.create_issue.await_args.args
    assert supplied_scope is scope
    assert repository == "owner/repo"
    assert body.title == "Issue"
    assert call_id == "issue-call"
