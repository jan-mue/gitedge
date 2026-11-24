"""Selected-repository authorization and durable forge publication behavior."""

import uuid
from typing import TYPE_CHECKING

import pytest

from app.agents.dependencies import AgentForgeScope
from app.clients.agent_repositories import AgentRepositoryClient
from app.clients.git.merges import GitMergeClient
from app.entities.repositories import Repository
from app.entities.users import User
from app.exceptions import InvalidInputError, PermissionDeniedError
from app.schemas.repositories import IssueCreate, IssueUpdate, PullRequestCreate, PullRequestUpdate
from app.services.activity import ActivityService
from app.services.agent_forge import AgentForgeService
from app.services.authorization import AuthorizationService
from app.services.issues import IssueService
from app.services.pull_requests import PullRequestService
from app.services.repositories import RepositoryService

if TYPE_CHECKING:
    from pytest_mock import MockerFixture

    from tests.unit.utils.fakes import FakeStores


BRANCH = "docs/update-readme"


@pytest.fixture
def forge_scope(fake_stores: FakeStores) -> AgentForgeScope:
    user = User(name="owner", lower_name="owner", email="owner@example.com", hashed_password="unused")
    fake_stores.users.persist(user)
    repo = Repository(name="repo", owner_id=user.id)
    fake_stores.repository.persist(repo)
    return AgentForgeScope(user_id=user.id, session_id=uuid.uuid4(), repository_ids=(repo.id,))


@pytest.fixture
def forge(fake_stores: FakeStores, mocker: MockerFixture) -> AgentForgeService:
    authorization = AuthorizationService(
        fake_stores.authorization, fake_stores.repository, fake_stores.organizations, fake_stores.users
    )
    activity = mocker.create_autospec(ActivityService, instance=True)
    pulls = PullRequestService(
        fake_stores.pull_requests,
        fake_stores.repository,
        mocker.create_autospec(RepositoryService, instance=True),
        activity,
        mocker.create_autospec(GitMergeClient, instance=True),
        authorization,
    )
    issues = IssueService(fake_stores.issues, fake_stores.repository, activity, authorization)
    sources = mocker.create_autospec(AgentRepositoryClient, instance=True)
    sources.publish_branch.return_value = BRANCH
    return AgentForgeService(sources, fake_stores.repository, fake_stores.users, authorization, pulls, issues)


@pytest.mark.parametrize("repository", ["repo", "/repo", "owner/", "owner/repo/extra"])
async def test_repository_names_must_have_exactly_one_owner_and_name(
    forge: AgentForgeService, forge_scope: AgentForgeScope, repository: str
) -> None:
    with pytest.raises(InvalidInputError, match="owner/name"):
        await forge.authorize(forge_scope, repository, "issues:write")


async def test_owned_but_unselected_repository_is_rejected_before_publication(
    forge: AgentForgeService, forge_scope: AgentForgeScope, fake_stores: FakeStores, mocker: MockerFixture
) -> None:
    publication = mocker.patch.object(forge.sources, "publish_branch")
    fake_stores.repository.persist(Repository(name="other", owner_id=forge_scope.user_id))
    with pytest.raises(PermissionDeniedError, match="not selected"):
        await forge.create_pull_request(forge_scope, mocker.Mock(), "owner/other", "Change", "Details", None, BRANCH)
    publication.assert_not_awaited()
    assert not fake_stores.pull_requests.items


async def test_inactive_account_cannot_create_an_issue(
    forge: AgentForgeService, forge_scope: AgentForgeScope, fake_stores: FakeStores
) -> None:
    user = await fake_stores.users.get(forge_scope.user_id)
    user.is_active = False
    with pytest.raises(PermissionDeniedError):
        await forge.create_issue(forge_scope, "owner/repo", IssueCreate(title="Issue"), "call")
    assert not fake_stores.issues.items


async def test_read_access_does_not_allow_publishing_git_changes(
    forge: AgentForgeService, forge_scope: AgentForgeScope, fake_stores: FakeStores, mocker: MockerFixture
) -> None:
    publication = mocker.patch.object(forge.sources, "publish_branch")
    reader = User(name="reader", lower_name="reader", email="reader@example.com", hashed_password="unused")
    fake_stores.users.persist(reader)
    scope = AgentForgeScope(
        user_id=reader.id, session_id=forge_scope.session_id, repository_ids=forge_scope.repository_ids
    )
    assert await forge.authorization.can(await fake_stores.repository.get(scope.repository_ids[0]), reader)
    with pytest.raises(PermissionDeniedError):
        await forge.create_pull_request(scope, mocker.Mock(), "owner/repo", "Change", "Details", None, BRANCH)
    publication.assert_not_awaited()
    assert not fake_stores.pull_requests.items


async def test_repeated_publication_reuses_the_pr_and_preserves_its_metadata(
    forge: AgentForgeService, forge_scope: AgentForgeScope, fake_stores: FakeStores, mocker: MockerFixture
) -> None:
    publication = mocker.patch.object(forge.sources, "publish_branch", return_value=BRANCH)
    activity = mocker.patch.object(forge.pulls.activity_service, "record")
    workspace = mocker.Mock()
    branch = BRANCH
    first = await forge.create_pull_request(forge_scope, workspace, "owner/repo", "Change", "Details", None, branch)
    repeated = await forge.create_pull_request(
        forge_scope, workspace, "owner/repo", "Other title", "Other body", None, branch
    )
    assert repeated.id == first.id
    assert repeated.number == first.number == 1
    assert repeated.title == "Change"
    assert repeated.body == "Details"
    assert repeated.head_branch == BRANCH
    assert repeated.base_branch == "main"
    assert len(fake_stores.pull_requests.items) == 1
    activity.assert_awaited_once()
    publication.assert_awaited_with(
        workspace,
        forge_scope.repository_ids[0],
        forge_scope.session_id,
        "main",
        branch,
    )


async def test_different_bases_have_distinct_pr_identities(
    forge: AgentForgeService, forge_scope: AgentForgeScope, fake_stores: FakeStores, mocker: MockerFixture
) -> None:
    branch = BRANCH
    first = await forge.create_pull_request(
        forge_scope, mocker.Mock(), "owner/repo", "Change", "Details", "main", branch
    )
    second = await forge.create_pull_request(
        forge_scope, mocker.Mock(), "owner/repo", "Change", "Details", "other", branch
    )
    assert first.id != second.id
    assert len(fake_stores.pull_requests.items) == 2


@pytest.mark.parametrize("own_branch", [True, False])
async def test_only_the_conversations_own_pr_receives_workspace_changes(
    forge: AgentForgeService,
    forge_scope: AgentForgeScope,
    fake_stores: FakeStores,
    mocker: MockerFixture,
    *,
    own_branch: bool,
) -> None:
    publication = mocker.patch.object(forge.sources, "publish_branch", return_value=BRANCH)
    user = await fake_stores.users.get(forge_scope.user_id)
    branch = BRANCH if own_branch else "someone-elses-branch"
    pull = await forge.pulls.create_pull_request(
        "owner",
        "repo",
        PullRequestCreate(title="Change", body="Original", head_branch=branch, base_branch="main"),
        user,
        pull_id=uuid.uuid5(forge_scope.session_id, f"pull:{forge_scope.repository_ids[0]}:{branch}:main")
        if own_branch
        else uuid.uuid4(),
    )
    result = await forge.update_pull_request(
        forge_scope, mocker.Mock(), "owner/repo", pull.number, PullRequestUpdate(body="Updated")
    )
    assert result.body == "Updated"
    assert result.head_branch == branch
    assert publication.await_count == int(own_branch)


async def test_issue_creation_is_idempotent_per_tool_call_and_updates_normally(
    forge: AgentForgeService, forge_scope: AgentForgeScope, fake_stores: FakeStores, mocker: MockerFixture
) -> None:
    publication = mocker.patch.object(forge.sources, "publish_branch")
    body = IssueCreate(title="Issue", body="Original")
    first = await forge.create_issue(forge_scope, "owner/repo", body, "first-call")
    repeated = await forge.create_issue(forge_scope, "owner/repo", body, "first-call")
    second = await forge.create_issue(forge_scope, "owner/repo", body, "second-call")
    assert first.id == repeated.id
    assert first.number == repeated.number == 1
    assert second.id != first.id
    assert second.number == 2
    assert len(fake_stores.issues.items) == 2
    updated = await forge.update_issue(forge_scope, "owner/repo", first.number, IssueUpdate(body="Updated"))
    assert updated.body == "Updated"
    assert updated.id == first.id
    publication.assert_not_awaited()
