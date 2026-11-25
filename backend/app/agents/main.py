"""Restate endpoint: one serialized virtual object per conversation."""

import json
import logging
import uuid
from functools import cache, partial
from pathlib import Path  # noqa: TC003 - Restate evaluates run_typed callback annotations
from typing import TYPE_CHECKING

import restate
from ag_ui.core import CustomEvent, RunErrorEvent, RunFinishedEvent, RunStartedEvent
from anyio import Path as AsyncPath
from pydantic_ai.exceptions import UnexpectedModelBehavior, UsageLimitExceeded, UserError
from pydantic_ai.messages import ModelMessagesTypeAdapter
from pydantic_ai.workspaces import CommandResult, Workspace, WorkspaceBackend, WorkspaceError, WorkspaceRef
from pydantic_ai_harness.smol_sandbox import SmolSandbox, SmolSandboxBackend
from smol import AsyncMachine, ConnectOptions
from uncalled_for import FailedDependency, Provided

from app.agents.cancellation import run_cancellable
from app.agents.coding import run_coding_agent
from app.agents.dependencies import (
    AccountModelDep,
    AgentSessionDepsDep,
    CodingAgentDeps,
    RunDepsDep,
    SetupAgentDeps,
    inject,
)
from app.agents.setup import run_setup_agent
from app.clients.agent_repositories import configure_git, prepare_environment
from app.clients.agent_streams import AgentRunCancelledError
from app.clients.agent_traces import capture_traces, capture_worktrees
from app.config import settings
from app.exceptions import ApplicationError
from app.sandboxes.vercel import VercelSandbox, VercelSandboxBackend
from app.schemas.agent_turns import AgentTurnRequest

if TYPE_CHECKING:
    from starlette.types import ASGIApp


logger = logging.getLogger(__name__)
agent_sessions = restate.VirtualObject(
    "GitEdgeAgents",
    invocation_retry_policy=restate.InvocationRetryPolicy(max_attempts=3, on_max_attempts="pause"),
)
STEP_RETRIES = restate.RunOptions(max_attempts=3)
CLEANUP_RETRIES = restate.RunOptions(max_attempts=1)
AGENT_ERRORS = (
    UsageLimitExceeded,
    UserError,
    UnexpectedModelBehavior,
    WorkspaceError,
    restate.TerminalError,
    NameError,
    TypeError,
    ValueError,
)
ERROR_CODES = {error.__name__ for error in (*AGENT_ERRORS, AgentRunCancelledError)}
agent_turns = restate.Service(
    "GitEdgeAgentTurns",
    ingress_private=True,
    invocation_retry_policy=restate.InvocationRetryPolicy(max_attempts=3, on_max_attempts="pause"),
)


async def workspace_backend(
    deps: SetupAgentDeps | CodingAgentDeps, name: str, snapshot_id: str | None = None, ref: WorkspaceRef | None = None
) -> WorkspaceBackend:
    """Build the selected provider's native workspace, without a custom lifecycle interface."""
    sandbox = deps.sandbox
    if isinstance(sandbox, VercelSandbox):
        return VercelSandboxBackend(sandbox.client, name=name, ref=ref, snapshot_id=snapshot_id)
    if not isinstance(sandbox, SmolSandbox):
        raise UserError("Unsupported sandbox capability")
    if ref is not None:
        return sandbox.backend(ref)
    if snapshot_id is not None:
        machine = await AsyncMachine.restore_checkpoint(
            snapshot_id, f"pydantic-ai-{uuid.uuid4().hex}", ConnectOptions(target="local")
        )
        return SmolSandboxBackend(sandbox=machine, working_dir=sandbox.working_dir, env=sandbox.env)
    return SmolSandboxBackend(
        image=sandbox.image,
        cpus=sandbox.cpus,
        memory_mb=sandbox.memory_mb,
        allow_internet_access=sandbox.allow_internet_access,
        working_dir=sandbox.working_dir,
        env=sandbox.env,
    )


async def snapshot_workspace(backend: WorkspaceBackend, *, checkpoint_dir: Path | None = None) -> str:
    """Use provider-native Vercel snapshots and local Smol VM checkpoints."""
    if isinstance(backend, VercelSandboxBackend):
        return await backend.snapshot()
    if not isinstance(backend, SmolSandboxBackend):
        raise UserError("Unsupported workspace provider")
    directory = await AsyncPath(checkpoint_dir or settings.AGENTS_SMOL_CHECKPOINT_DIR).expanduser()
    directory = await directory.resolve()
    await directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    machine = await backend.get_sandbox()
    checkpoint = await machine.checkpoint(str(directory / f"{uuid.uuid4().hex}.smolcheckpoint"))
    return checkpoint.id


async def stop_workspace(backend: WorkspaceBackend) -> None:
    """Let each provider own cleanup; Smol deletion stays in the upstream capability."""
    if isinstance(backend, VercelSandboxBackend):
        await backend.stop()
    elif backend.ref is not None:
        await SmolSandbox().destroy(backend.ref)


def failure_code(error: Exception) -> str:
    """Preserve known child failure categories without exposing provider error messages."""
    if isinstance(error, restate.TerminalError) and error.message in ERROR_CODES:
        return error.message
    if isinstance(error, WorkspaceError):
        return "WorkspaceError"
    return type(error).__name__


@agent_turns.handler()
@inject
async def run_agent_turn(
    _ctx: restate.Context,
    request: AgentTurnRequest,
    deps: RunDepsDep = Provided,
    model: AccountModelDep = Provided,
) -> list[dict]:
    """Journal the agent result independently of later snapshot/storage/cleanup replay."""
    try:
        for resource in (deps, model):
            if isinstance(resource, FailedDependency):
                raise resource.error
        machine = await workspace_backend(deps, f"gitedge-{request.run_id}", ref=request.workspace)
        history = ModelMessagesTypeAdapter.validate_python(request.history)
        if isinstance(deps, CodingAgentDeps):
            messages = await run_coding_agent(
                deps,
                workspace=machine,
                run_id=request.run_id,
                session_id=request.session_id,
                prompt=request.prompt,
                model=model,
                instructions=request.instructions,
                history=history,
                finish_stream=False,
            )
        else:
            messages = await run_setup_agent(
                deps,
                workspace=machine,
                run_id=request.run_id,
                session_id=request.session_id,
                prompt=request.prompt,
                model=model,
                instructions=request.instructions,
                history=history,
                finish_stream=False,
            )
        return json.loads(ModelMessagesTypeAdapter.dump_json(messages))
    except AGENT_ERRORS as error:
        code = failure_code(error)
        logger.warning("Agent execution %s failed (%s)", request.run_id, code)
        raise restate.TerminalError(code) from error


@agent_sessions.handler()
@inject
async def run(ctx: restate.ObjectContext, run_id: str, resources: AgentSessionDepsDep = Provided) -> str:
    """Authorize at execution time, resume tools lazily, and durably publish a terminal state."""
    if isinstance(resources, FailedDependency):
        raise resources.error
    store = resources.store
    turn = await store.run(uuid.UUID(run_id))
    if turn is None:
        raise restate.TerminalError("Agent run unavailable")
    session = await store.get(turn.session_id)
    if str(session.id) != ctx.key():
        raise restate.TerminalError("Conversation mismatch")
    deps = resources.agent
    streams = deps.streams
    started = RunStartedEvent(thread_id=str(session.id), run_id=run_id)
    await ctx.run_typed(
        "publish started turn",
        partial(streams.append, run_id, "start", started.model_dump_json(by_alias=True)),
        STEP_RETRIES,
    )
    machine: WorkspaceBackend | None = None

    async def load_input() -> dict:
        if await streams.cancelled(run_id):
            raise AgentRunCancelledError("Run stopped")
        user = await resources.users.get(session.user_id)
        environment = await store.environment(session.environment_id)
        if not user.is_active or environment is None or environment.user_id != user.id:
            raise restate.TerminalError("Environment access revoked")
        repositories = resources.repositories
        authorization = resources.authorization
        members = await store.repositories(environment.id)
        try:
            for member in members:
                await authorization.require(await repositories.get(member), user)
        except ApplicationError as error:
            raise restate.TerminalError("Repository access revoked") from error
        return {
            "status": turn.status,
            "prompt": turn.prompt,
            "model": turn.model,
            "user_id": str(user.id),
            "author_name": user.display_name or user.name,
            "author_email": str(user.email),
            "environment_id": str(environment.id),
            "snapshot": session.snapshot_id or environment.snapshot_id,
            "setup": session.kind == "setup" and not await store.history(session.id),
            "script": environment.setup_script,
            "instructions": environment.instructions,
            "history": await store.history(session.id),
            "repositories": [str(item) for item in members],
        }

    try:
        data = await ctx.run_typed("load authorized turn", load_input, STEP_RETRIES)
        if data["status"] in {"completed", "failed", "cancelled"}:
            return run_id
        await ctx.run_typed("mark running", partial(store.start, turn), STEP_RETRIES)

        async def prepare_workspace() -> dict[str, str]:
            nonlocal machine
            machine = await workspace_backend(deps, f"gitedge-{run_id}", data["snapshot"])
            await machine.working_dir()
            ref = machine.ref
            if ref is None:
                raise RuntimeError("Sandbox did not report its workspace ref")
            return {"provider": ref.provider, "id": ref.id}

        saved_ref = await ctx.run_typed("prepare workspace", prepare_workspace, STEP_RETRIES)
        if machine is None:
            machine = await workspace_backend(deps, f"gitedge-{run_id}", ref=WorkspaceRef(**saved_ref))
        members = [uuid.UUID(item) for item in data["repositories"]]
        setup_results: list[dict[str, str | int]] = []
        if data["setup"]:
            setup_workspace = Workspace(machine)

            async def setup_command(command: str) -> CommandResult:
                result = await run_cancellable(
                    partial(setup_workspace.run, command, shell=True, timeout=900),  # noqa: S604 - isolated setup script
                    lambda: streams.cancelled(run_id),
                )
                command_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"setup:{run_id}:{command}"))
                for stream, chunk in (("stdout", result.stdout), ("stderr", result.stderr)):
                    if chunk:
                        event = CustomEvent(
                            name="bash_output",
                            value={"command_id": command_id, "stream": stream, "chunk": chunk, "sequence": 0},
                        )
                        await streams.append(
                            run_id, f"setup:{command_id}:{stream}:0", event.model_dump_json(by_alias=True)
                        )
                return result

            setup_results = await ctx.run_typed(
                "prepare repositories",
                partial(
                    prepare_environment,
                    machine,
                    deps.blobs,
                    uuid.UUID(data["environment_id"]),
                    members,
                    data["script"],
                    data["instructions"],
                    execute=setup_command,
                ),
                STEP_RETRIES,
            )
        await ctx.run_typed(
            "configure Git",
            partial(configure_git, machine, members, data["author_name"], data["author_email"]),
            STEP_RETRIES,
        )
        baseline = await ctx.run_typed("capture baseline", partial(capture_worktrees, machine, members), STEP_RETRIES)
        messages = await ctx.service_call(
            run_agent_turn,
            arg=AgentTurnRequest(
                run_id=run_id,
                session_id=str(session.id),
                user_id=uuid.UUID(data["user_id"]),
                prompt=data["prompt"],
                model=data["model"],
                instructions=data["instructions"]
                + (
                    "\nThis is a setup chat. The saved setup scripts have already run. "
                    "If the results satisfy the requested setup, report readiness without further tools or edits. "
                    "Otherwise repair failed commands or missing requirements and save reproducible setup.sh and "
                    "instructions.md in each repository's .gitedge/agents directory. Setup results: "
                    + json.dumps(setup_results)
                    if data["setup"]
                    else ""
                )
                + "\nRepository paths: "
                + ", ".join(f"/workspace/{member}" for member in members)
                + ". Before changing a repository, read its AGENTS.md and .gitedge/agents/instructions.md.",
                history=data["history"],
                workspace=WorkspaceRef(**saved_ref),
                repository_ids=members,
                coding=session.kind == "coding",
            ),
        )
        traces = await ctx.run_typed(
            "capture attribution", partial(capture_traces, machine, members, baseline), STEP_RETRIES
        )
        snapshot = await ctx.run_typed("snapshot sandbox", partial(snapshot_workspace, machine), STEP_RETRIES)
        serialized = messages[len(data["history"]) :]
        await ctx.run_typed(
            "save completed turn", partial(store.finish, turn, session, snapshot, serialized, traces), STEP_RETRIES
        )
        await ctx.run_typed("stop sandbox", partial(stop_workspace, machine), STEP_RETRIES)
        event = RunFinishedEvent(thread_id=str(session.id), run_id=run_id)
        await ctx.run_typed(
            "publish completed turn",
            partial(streams.append, run_id, "terminal", event.model_dump_json(by_alias=True)),
            STEP_RETRIES,
        )
        return run_id
    except AGENT_ERRORS as error:
        logger.warning("Agent turn %s failed (%s)", run_id, type(error).__name__)
        # Never expose provider responses, repository data, or credential errors in notifications.
        code = failure_code(error)
        await ctx.run_typed("save failed turn", partial(store.fail, turn, code), STEP_RETRIES)
        failure = RunErrorEvent(message="Agent run failed", code=code)
        await ctx.run_typed(
            "publish failed turn",
            partial(streams.append, run_id, "terminal", failure.model_dump_json(by_alias=True)),
            STEP_RETRIES,
        )
        if machine is not None:
            try:
                snapshot = await ctx.run_typed(
                    "snapshot failed turn", partial(snapshot_workspace, machine), CLEANUP_RETRIES
                )
                await ctx.run_typed("save failed image", partial(store.save_snapshot, session, snapshot), STEP_RETRIES)
            except (
                restate.TerminalError,
                WorkspaceError,
                UserError,
                NameError,
                TypeError,
                ValueError,
            ) as cleanup_error:
                logger.warning("Unable to snapshot failed turn %s (%s)", run_id, type(cleanup_error).__name__)
            try:
                await ctx.run_typed("stop failed sandbox", partial(stop_workspace, machine), CLEANUP_RETRIES)
            except (
                restate.TerminalError,
                WorkspaceError,
                UserError,
                NameError,
                TypeError,
                ValueError,
            ) as cleanup_error:
                logger.warning("Unable to stop failed sandbox for %s (%s)", run_id, type(cleanup_error).__name__)
        return run_id


@cache
def restate_app() -> ASGIApp:
    """Expose a signed request-response ASGI endpoint compatible with Vercel Functions."""
    keys = [settings.RESTATE_IDENTITY_PUBLIC_KEY] if settings.RESTATE_IDENTITY_PUBLIC_KEY else []
    if settings.VERCEL_ENV != "development" and not keys:
        raise RuntimeError("Restate endpoint identity verification is required")
    return restate.app(services=[agent_sessions, agent_turns], protocol="request_response", identity_keys=keys)
