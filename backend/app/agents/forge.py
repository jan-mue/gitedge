"""PydanticAI capability for GitEdge PR and issue operations."""

from dataclasses import dataclass
from typing import Literal, override

from pydantic_ai import ModelRetry, RunContext
from pydantic_ai.capabilities import AbstractCapability
from pydantic_ai.exceptions import UserError
from pydantic_ai.toolsets import FunctionToolset

from app.agents.dependencies import CodingAgentDeps
from app.entities.issues import IssueState
from app.exceptions import ApplicationError
from app.schemas.repositories import IssueCreate, IssueUpdate, PullRequestUpdate

tools = FunctionToolset[CodingAgentDeps](id="gitedge_forge")


@tools.tool
async def create_pull_request(
    ctx: RunContext[CodingAgentDeps],
    repository: str,
    title: str,
    body: str,
    head_branch: str,
    base_branch: str | None = None,
) -> dict[str, str | int]:
    """Publish an existing committed Git branch and open or reuse its GitEdge PR.

    Args:
        ctx: The authorized agent run context.
        repository: Selected repository in owner/name format.
        title: PR title; commit messages are created with Git, not this tool.
        body: Markdown description, including actual validation results.
        head_branch: The conversation branch already created and committed with Git.
        base_branch: Base branch; defaults to the repository's default branch.
    """
    try:
        pull = await ctx.deps.forge.create_pull_request(
            ctx.deps.forge_scope, ctx.workspace, repository, title, body, base_branch, head_branch
        )
    except ApplicationError as error:
        raise ModelRetry(str(error.detail)) from error
    return {
        "number": pull.number,
        "url": f"/{pull.repo_owner}/{pull.repo_name}/pulls/{pull.number}",
        "title": pull.title,
        "head_branch": pull.head_branch,
    }


@tools.tool
async def update_pull_request(
    ctx: RunContext[CodingAgentDeps],
    repository: str,
    number: int,
    title: str | None = None,
    body: str | None = None,
    state: Literal["open", "closed"] | None = None,
) -> dict[str, str | int]:
    """Update a GitEdge PR; a PR from this chat also receives its already-committed Git changes."""
    try:
        pull = await ctx.deps.forge.update_pull_request(
            ctx.deps.forge_scope,
            ctx.workspace,
            repository,
            number,
            PullRequestUpdate(title=title, body=body, state=IssueState(state) if state else None),
        )
    except ApplicationError as error:
        raise ModelRetry(str(error.detail)) from error
    return {
        "number": pull.number,
        "url": f"/{pull.repo_owner}/{pull.repo_name}/pulls/{pull.number}",
        "title": pull.title,
        "state": pull.state.value,
    }


@tools.tool
async def create_issue(
    ctx: RunContext[CodingAgentDeps], repository: str, title: str, body: str
) -> dict[str, str | int]:
    """Create a GitEdge issue in a selected repository."""
    if ctx.tool_call_id is None:
        raise UserError("Issue creation needs a stable tool call ID")
    try:
        issue = await ctx.deps.forge.create_issue(
            ctx.deps.forge_scope, repository, IssueCreate(title=title, body=body), ctx.tool_call_id
        )
    except ApplicationError as error:
        raise ModelRetry(str(error.detail)) from error
    return {
        "number": issue.number,
        "url": f"/{issue.repo_owner}/{issue.repo_name}/issues/{issue.number}",
        "title": issue.title,
    }


@tools.tool
async def update_issue(
    ctx: RunContext[CodingAgentDeps],
    repository: str,
    number: int,
    title: str | None = None,
    body: str | None = None,
    state: Literal["open", "closed"] | None = None,
) -> dict[str, str | int]:
    """Update the title, Markdown description or open/closed state of a GitEdge issue."""
    try:
        issue = await ctx.deps.forge.update_issue(
            ctx.deps.forge_scope,
            repository,
            number,
            IssueUpdate(title=title, body=body, state=IssueState(state) if state else None),
        )
    except ApplicationError as error:
        raise ModelRetry(str(error.detail)) from error
    return {
        "number": issue.number,
        "url": f"/{issue.repo_owner}/{issue.repo_name}/issues/{issue.number}",
        "title": issue.title,
        "state": issue.state.value,
    }


@dataclass(kw_only=True)
class GitEdgeForge(AbstractCapability[CodingAgentDeps]):
    """Publish changes and collaborate through backend services, never sandbox credentials."""

    id: str | None = "gitedge_forge"

    @override
    def get_toolset(self) -> FunctionToolset[CodingAgentDeps]:
        return tools

    @override
    def get_instructions(self) -> str:
        return (
            "Choose a descriptive branch name, create it, and switch to it before editing or committing. "
            "Use real git switch -c commands, or git branch followed by git switch. "
            "Use git -C with the repository path or cd to that path in every shell call; cd does not persist across calls. "
            "Stage the intended files with git add and create commits with git commit, including meaningful messages. "
            "Do not commit .gitedge/agents setup metadata. Git identity is already configured. "
            "When asked to open a PR, use create_pull_request with your chosen head_branch to publish the existing commits. "
            "The tool never stages files, creates commits, or rewrites the branch. "
            "Do not git push or put forge credentials in the workspace. Keep the base branch unchanged. "
            "Include only actual validation results. Use update_pull_request, create_issue and update_issue for "
            "follow-up collaboration. Repositories use owner/name and must belong to this environment. "
            "Return the tool's PR/issue URL to the user."
        )
