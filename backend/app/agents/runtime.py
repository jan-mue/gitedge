"""Restate endpoint: one serialized virtual object per conversation."""

import json
import logging
import uuid
from typing import TYPE_CHECKING

import restate
from ag_ui.core import CustomEvent, RunErrorEvent, RunFinishedEvent, RunStartedEvent
from k8s_agent_sandbox import SandboxClient as KubernetesClient
from pydantic_ai.exceptions import UnexpectedModelBehavior, UsageLimitExceeded, UserError
from pydantic_ai.messages import ModelMessagesTypeAdapter
from redis.asyncio import Redis
from upstash_redis.asyncio import Redis as UpstashRedis

from app.agents.coding import run_coding_agent
from app.agents.providers import account_model
from app.agents.sandbox import RunSandbox
from app.agents.workspace import SandboxWorkspace
from app.clients.agent_repositories import prepare_environment
from app.clients.agent_streams import AgentRunCancelledError, AgentStreamStore
from app.clients.agent_traces import capture_traces, capture_worktrees
from app.clients.agents import AgentStore
from app.clients.authorization import SQLAuthorizationStore
from app.clients.database import create_db_engine, create_session_factory
from app.clients.organizations import SQLOrganizationStore
from app.clients.repositories import SQLRepositoryStore
from app.clients.sandbox.kubernetes import KubernetesAgentSandbox
from app.clients.sandbox.vercel import VercelSandboxClient
from app.clients.users import SQLUserStore
from app.config import settings
from app.exceptions import ApplicationError
from app.services.authorization import AuthorizationService

if TYPE_CHECKING:
    from pydantic_ai.workspaces import CommandResult
    from starlette.types import ASGIApp

    from app.clients.sandbox import SnapshotableSandboxClient

logger = logging.getLogger(__name__)
agent_sessions = restate.VirtualObject("GitEdgeAgents")
STEP_RETRIES = restate.RunOptions(max_attempts=3)


def stream_store() -> AgentStreamStore:
    """Select the same TCP versus REST transports used elsewhere in the app."""
    if settings.REDIS_KIND == "rest":
        return AgentStreamStore(UpstashRedis(url=settings.REDIS_URL, token=settings.REDIS_PASSWORD or ""))
    return AgentStreamStore(Redis.from_url(settings.REDIS_URL, password=settings.REDIS_PASSWORD, decode_responses=True))


def sandbox_client() -> SnapshotableSandboxClient:
    """Resolve the tool-execution provider without starting a machine."""
    if settings.AGENTS_SANDBOX == "vercel":
        return VercelSandboxClient()
    from app.api.dependencies import get_blob_client  # noqa: PLC0415 - application composition

    return KubernetesAgentSandbox(
        KubernetesClient(),
        get_blob_client(),
        warmpool=settings.AGENTS_KUBERNETES_WARMPOOL,
        namespace=settings.AGENTS_KUBERNETES_NAMESPACE,
    )


@agent_sessions.handler()
async def run(ctx: restate.ObjectContext, run_id: str) -> str:
    """Authorize at execution time, resume tools lazily, and durably publish a terminal state."""
    async with create_db_engine() as engine, create_session_factory(engine)() as db:
        store = AgentStore(db)
        turn = await store.run(uuid.UUID(run_id))
        if turn is None:
            raise restate.TerminalError("Agent run unavailable")
        session = await store.get(turn.session_id)
        if str(session.id) != ctx.key():
            raise restate.TerminalError("Conversation mismatch")
        streams = stream_store()
        started = RunStartedEvent(thread_id=str(session.id), run_id=run_id)
        await ctx.run_typed(
            "publish started turn",
            lambda: streams.append(run_id, "start", started.model_dump_json(by_alias=True)),
            STEP_RETRIES,
        )
        machine: RunSandbox | None = None

        async def load_input() -> dict:
            if not settings.AGENTS_ENABLED:
                raise restate.TerminalError("Agents are disabled")
            user = await SQLUserStore(db).get(session.user_id)
            environment = await store.environment(session.environment_id)
            if not user.is_active or environment is None or environment.user_id != user.id:
                raise restate.TerminalError("Environment access revoked")
            repositories = SQLRepositoryStore(db)
            authorization = AuthorizationService(
                SQLAuthorizationStore(db), repositories, SQLOrganizationStore(db), SQLUserStore(db)
            )
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
            if await streams.cancelled(run_id):
                raise AgentRunCancelledError("Run stopped")
            history = ModelMessagesTypeAdapter.validate_python(data["history"])
            turn.status = "running"
            await ctx.run_typed("mark running", lambda: store.save_run(turn), STEP_RETRIES)
            machine = RunSandbox(sandbox_client, f"gitedge-{run_id}", data["snapshot"])
            members = [uuid.UUID(item) for item in data["repositories"]]
            setup_results: list[dict[str, str | int]] = []
            if data["setup"]:
                from app.api.dependencies import get_blob_client  # noqa: PLC0415 - application composition

                async def setup_output(stream: str, line: str, command_id: str, sequence: int) -> None:
                    event = CustomEvent(
                        name="bash_output",
                        value={"command_id": command_id, "stream": stream, "chunk": line, "sequence": sequence},
                    )
                    await streams.append(
                        run_id, f"setup:{command_id}:{stream}:{sequence}", event.model_dump_json(by_alias=True)
                    )

                setup_workspace = SandboxWorkspace(
                    machine, f"{run_id}-setup", setup_output, lambda: streams.cancelled(run_id)
                )

                async def setup_command(command: str) -> CommandResult:
                    return await setup_workspace.run(command, shell=True, timeout=900)  # noqa: S604 - executes inside the isolated sandbox

                setup_results = await ctx.run_typed(
                    "prepare repositories",
                    lambda: prepare_environment(
                        machine,
                        get_blob_client(),
                        uuid.UUID(data["environment_id"]),
                        members,
                        data["script"],
                        data["instructions"],
                        execute=setup_command,
                    ),
                    STEP_RETRIES,
                )
            baseline = await ctx.run_typed(
                "capture baseline", lambda: capture_worktrees(machine, members), STEP_RETRIES
            )
            async with account_model(
                data["model"], uuid.UUID(data["user_id"]), create_session_factory(engine)
            ) as model:
                messages = await run_coding_agent(
                    machine,
                    streams,
                    run_id=run_id,
                    session_id=str(session.id),
                    prompt=data["prompt"],
                    model=model,
                    instructions=data["instructions"]
                    + (
                        "\nThis is a setup chat. Install dependencies, repair any failed setup commands, and save reproducible setup.sh and instructions.md in each repository's .gitedge/agents directory. Setup results: "
                        + json.dumps(setup_results)
                        if data["setup"]
                        else ""
                    )
                    + "\nRepositories are in /workspace/<repository UUID>. Read each repository AGENTS.md and .gitedge/agents/instructions.md before working.",
                    history=history,
                    finish_stream=False,
                )
            traces = await ctx.run_typed(
                "capture attribution", lambda: capture_traces(machine, members, baseline), STEP_RETRIES
            )
            snapshot = await ctx.run_typed("snapshot sandbox", lambda: machine.snapshot(run_id), STEP_RETRIES)
            serialized = json.loads(ModelMessagesTypeAdapter.dump_json(messages[len(history) :]))
            await ctx.run_typed("stop sandbox", machine.stop, STEP_RETRIES)
            await ctx.run_typed(
                "save completed turn", lambda: store.finish(turn, session, snapshot, serialized, traces), STEP_RETRIES
            )
            event = RunFinishedEvent(thread_id=str(session.id), run_id=run_id)
            await ctx.run_typed(
                "publish completed turn",
                lambda: streams.append(run_id, "terminal", event.model_dump_json(by_alias=True)),
                STEP_RETRIES,
            )
            return run_id
        except (UsageLimitExceeded, UserError, UnexpectedModelBehavior, restate.TerminalError) as error:
            logger.warning("Agent turn %s failed (%s)", run_id, type(error).__name__)
            # Never expose provider responses, repository data, or credential errors in notifications.
            code = type(error).__name__
            if machine is not None:
                try:
                    snapshot = await ctx.run_typed(
                        "snapshot failed turn", lambda: machine.snapshot(f"{run_id}-failed"), STEP_RETRIES
                    )
                    await ctx.run_typed(
                        "save failed image", lambda: store.update(session, {"snapshot_id": snapshot}), STEP_RETRIES
                    )
                except restate.TerminalError:
                    logger.warning("Unable to snapshot failed turn %s", run_id)
                await ctx.run_typed("stop failed sandbox", machine.stop, STEP_RETRIES)
            await ctx.run_typed("save failed turn", lambda: store.fail(turn, code), STEP_RETRIES)
            failure = RunErrorEvent(message="Agent run failed", code=code)
            await ctx.run_typed(
                "publish failed turn",
                lambda: streams.append(run_id, "terminal", failure.model_dump_json(by_alias=True)),
                STEP_RETRIES,
            )
            return run_id


def restate_app() -> ASGIApp:
    """Expose a signed request-response ASGI endpoint compatible with Vercel Functions."""
    keys = [settings.RESTATE_IDENTITY_PUBLIC_KEY] if settings.RESTATE_IDENTITY_PUBLIC_KEY else []
    if settings.VERCEL_ENV != "development" and not keys:
        raise RuntimeError("Restate endpoint identity verification is required")
    return restate.app(services=[agent_sessions], protocol="request_response", identity_keys=keys)
