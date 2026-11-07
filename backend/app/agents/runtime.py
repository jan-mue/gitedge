"""Restate endpoint: one serialized virtual object per conversation."""

import json
import uuid
from typing import TYPE_CHECKING

import restate
from ag_ui.core import RunErrorEvent, RunFinishedEvent
from k8s_agent_sandbox import SandboxClient as KubernetesClient
from pydantic_ai.exceptions import UnexpectedModelBehavior, UsageLimitExceeded, UserError
from pydantic_ai.messages import ModelMessagesTypeAdapter
from redis.asyncio import Redis
from upstash_redis.asyncio import Redis as UpstashRedis

from app.agents.coding import run_coding_agent
from app.clients.agent_repositories import prepare_environment
from app.clients.agent_streams import AgentStreamStore
from app.clients.agent_traces import capture_traces, capture_worktrees
from app.clients.agents import AgentStore
from app.clients.database import create_db_engine, create_session_factory
from app.clients.sandbox.kubernetes import KubernetesAgentSandbox
from app.clients.sandbox.vercel import VercelSandboxClient
from app.config import settings

if TYPE_CHECKING:
    from starlette.types import ASGIApp

    from app.clients.sandbox import SnapshotableSandboxClient

agent_sessions = restate.VirtualObject("GitEdgeAgents")


def stream_store() -> AgentStreamStore:
    """Select the same TCP versus REST transports used elsewhere in the app."""
    if settings.REDIS_URL.startswith("https://"):
        return AgentStreamStore(UpstashRedis(url=settings.REDIS_URL, token=settings.REDIS_PASSWORD or ""))
    return AgentStreamStore(Redis.from_url(settings.REDIS_URL, password=settings.REDIS_PASSWORD, decode_responses=True))


def sandbox_client() -> SnapshotableSandboxClient:
    """Resolve the tool-execution provider without starting a machine."""
    if settings.AGENTS_SANDBOX == "vercel":
        return VercelSandboxClient()
    from app.api.dependencies import get_blob_client  # noqa: PLC0415 - dependency cycle at composition boundary

    return KubernetesAgentSandbox(
        KubernetesClient(),
        get_blob_client(),
        warmpool=settings.AGENTS_KUBERNETES_WARMPOOL,
        namespace=settings.AGENTS_KUBERNETES_NAMESPACE,
    )


@agent_sessions.handler()
async def run(ctx: restate.ObjectContext, run_id: str) -> str:
    """Resume one turn durably; the virtual object prevents overlapping machines."""
    machine = sandbox_client()
    async with create_db_engine() as engine, create_session_factory(engine)() as db:
        store = AgentStore(db)

        async def load_input() -> dict:
            turn = await store.run(uuid.UUID(run_id))
            if turn is None or not settings.AGENTS_ENABLED:
                raise restate.TerminalError("Agent run unavailable")
            session = await store.get(turn.session_id)
            environment = await store.environment(session.environment_id)
            if environment is None:
                raise restate.TerminalError("Environment unavailable")
            return {
                "status": turn.status,
                "prompt": turn.prompt,
                "model": turn.model,
                "session_id": str(session.id),
                "snapshot": session.snapshot_id or environment.snapshot_id,
                "setup": session.kind == "setup" and not session.snapshot_id,
                "script": environment.setup_script,
                "instructions": environment.instructions,
                "history": await store.history(session.id),
                "repositories": [str(item) for item in await store.repositories(environment.id)],
            }

        data = await ctx.run_typed("load turn input", load_input)
        turn = await store.run(uuid.UUID(run_id))
        if turn is None or not settings.AGENTS_ENABLED:
            raise restate.TerminalError("Agent run unavailable")
        session = await store.get(turn.session_id)
        if str(session.id) != ctx.key():
            raise restate.TerminalError("Conversation mismatch")
        if data["status"] == "completed":
            return run_id
        environment = await store.environment(session.environment_id)
        if environment is None:
            raise restate.TerminalError("Environment unavailable")
        history = ModelMessagesTypeAdapter.validate_python(data["history"])
        turn.status = "running"
        await ctx.run_typed("mark running", lambda: store.save_run(turn))
        name = f"gitedge-{run_id}"
        await ctx.run_typed("start sandbox", lambda: machine.start(name, data["snapshot"]))
        # Attach on every replay: handles are process-local, unlike the named machine.
        await machine.start(name, data["snapshot"])
        try:
            if data["setup"]:
                from app.api.dependencies import get_blob_client  # noqa: PLC0415 - composition boundary

                repository_ids = [uuid.UUID(item) for item in data["repositories"]]
                await ctx.run_typed(
                    "prepare repositories",
                    lambda: prepare_environment(
                        machine, get_blob_client(), environment.id, repository_ids, data["script"], data["instructions"]
                    ),
                )
            repository_ids = [uuid.UUID(item) for item in data["repositories"]]
            baseline = await ctx.run_typed("capture baseline", lambda: capture_worktrees(machine, repository_ids))
            messages = await run_coding_agent(
                machine,
                stream_store(),
                run_id=run_id,
                session_id=str(session.id),
                prompt=data["prompt"],
                model=data["model"],
                instructions=data["instructions"]
                + "\nRepositories are in /workspace/<repository UUID>. Inspect those directories and read each repository AGENTS.md and .gitedge/agents/instructions.md before working.",
                history=history,
                finish_stream=False,
            )
            repository_ids = [uuid.UUID(item) for item in data["repositories"]]
            traces = await ctx.run_typed(
                "capture attribution", lambda: capture_traces(machine, repository_ids, baseline)
            )
            snapshot = await ctx.run_typed("snapshot sandbox", lambda: machine.snapshot(run_id))
            serialized = json.loads(ModelMessagesTypeAdapter.dump_json(messages[len(history) :]))
            await ctx.run_typed("stop sandbox", machine.stop)
            await ctx.run_typed(
                "save completed turn", lambda: store.finish(turn, session, snapshot, serialized, traces)
            )
            event = RunFinishedEvent(thread_id=str(session.id), run_id=run_id)
            await stream_store().append(run_id, "terminal", event.model_dump_json(by_alias=True))
        except (UsageLimitExceeded, UserError, UnexpectedModelBehavior) as error:
            message = type(error).__name__
            failed_snapshot = await ctx.run_typed("snapshot failed turn", lambda: machine.snapshot(run_id))
            await ctx.run_typed("save failed image", lambda: store.update(session, {"snapshot_id": failed_snapshot}))
            await ctx.run_typed("save failed turn", lambda: store.fail(turn, message))
            await ctx.run_typed("stop failed sandbox", machine.stop)
            event = RunErrorEvent(message="Agent run failed", code=message)
            await stream_store().append(run_id, "terminal", event.model_dump_json(by_alias=True))
            raise restate.TerminalError(message) from error
        return run_id


def restate_app() -> ASGIApp:
    """Expose a request-response ASGI endpoint compatible with Vercel Functions."""
    keys = [settings.RESTATE_IDENTITY_PUBLIC_KEY] if settings.RESTATE_IDENTITY_PUBLIC_KEY else []
    if settings.VERCEL_ENV != "development" and not keys:
        raise RuntimeError("Restate endpoint identity verification is required")
    return restate.app(services=[agent_sessions], protocol="request_response", identity_keys=keys)
