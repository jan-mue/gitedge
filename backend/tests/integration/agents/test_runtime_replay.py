import asyncio
import json
import logging
import os
import shutil
import uuid
from typing import TYPE_CHECKING

import anyio
import pytest
import restate
from fastapi import FastAPI
from redis.asyncio import Redis
from sqlalchemy import select

from app.agents.main import restate_app, run
from app.clients.agent_credentials import AgentCredentialStore
from app.clients.agent_streams import AgentStreamStore
from app.clients.agents import AgentStore
from app.clients.database import create_db_engine, create_session_factory
from app.config import Settings, settings
from app.entities.agents import AgentEnvironment, AgentRun, AgentSession
from app.entities.users import User
from tests.integration.agents.containers import OLLAMA_MODEL, RESTATE_IMAGE

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from pathlib import Path

    from pydantic_ai_harness.smol_sandbox import SmolSandbox
    from starlette.types import Receive, Scope, Send
    from testcontainers.community.ollama import OllamaContainer


async def log_invocation_failures(admin_url: str) -> None:
    """Capture real invocation journals before the SDK harness destroys its server."""
    cli = shutil.which("restate")
    if cli is None:
        logger.error("Restate CLI is unavailable for failure diagnostics")
        return
    env = {**os.environ, "RESTATE_ADMIN_URL": admin_url, "RESTATE_AUTH_TOKEN": ""}
    result = await anyio.run_process([cli, "invocations", "list", "--all", "--json"], env=env, check=False)
    logger.error("Restate invocations: %s", result.stdout.decode())
    if result.returncode != 0:
        logger.error("Restate CLI failed: %s", result.stderr.decode())
        return
    for item in json.loads(result.stdout)["invocations"]:
        invocation_id = item.get("id") or item.get("invocation_id")
        if isinstance(invocation_id, str):
            details = await anyio.run_process(
                [cli, "invocations", "describe", invocation_id, "--json"], env=env, check=False
            )
            logger.error("Restate invocation details: %s", details.stdout.decode())


@pytest.mark.parametrize("outcome", ["completed", "cancelled"])
async def test_turn_status_survives_cleanup_replay(
    infrastructure: dict[str, str],
    agent_ollama: OllamaContainer,
    smol_sandbox_capability: SmolSandbox,
    tmp_path: Path,
    outcome: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for name, value in infrastructure.items():
        monkeypatch.setenv(name, value)
    configured = Settings()
    for name in infrastructure.keys() & Settings.model_fields.keys():
        monkeypatch.setattr(settings, name, getattr(configured, name))
    monkeypatch.setattr(settings, "AGENTS_OPENAI_ENDPOINTS", {"ollama": f"{agent_ollama.get_endpoint()}/v1"})
    monkeypatch.setattr(settings, "AGENTS_SMOL_CHECKPOINT_DIR", tmp_path)
    monkeypatch.setattr(settings, "AGENTS_SANDBOX", "smol")
    monkeypatch.setattr(settings, "AGENTS_SMOL_IMAGE", smol_sandbox_capability.image)
    monkeypatch.setattr(settings, "AGENTS_SMOL_MEMORY_MB", smol_sandbox_capability.memory_mb)
    checkpoint = None
    try:
        async with (
            create_db_engine() as engine,
            create_session_factory(engine)() as db,
            Redis.from_url(infrastructure["REDIS_URL"], decode_responses=True) as client,
        ):
            agent_streams = AgentStreamStore(client)
            user = await db.scalar(select(User).where(User.email == "admin@example.com"))
            assert user is not None
            credentials = AgentCredentialStore(db)
            await credentials.save_secret(user.id, "ollama", "Replay integration", "ollama")
            store = AgentStore(db)
            environment = AgentEnvironment(id=uuid.uuid4(), user_id=user.id, name="Replay integration")
            await store.create_environment(environment, [])
            session = AgentSession(
                id=uuid.uuid4(),
                user_id=user.id,
                environment_id=environment.id,
                title="Replay integration",
                kind="setup",
            )
            await store.add(session)
            turn = await store.create_run(
                AgentRun(
                    id=uuid.uuid4(),
                    session_id=session.id,
                    request_id=str(uuid.uuid4()),
                    model=f"ollama:{OLLAMA_MODEL}",
                    prompt="Reply hello. Do not use any tools.",
                )
            )

            app = FastAPI()
            app.mount("/restate", restate_app())

            async def endpoint(scope: Scope, receive: Receive, send: Send) -> None:
                if scope["type"] == "http":
                    scope = {**scope, "path": f"/restate{scope['path']}", "raw_path": b"/restate" + scope["raw_path"]}
                await app(scope, receive, send)

            # The harness forces journal replay at each step, including after VM deletion.
            async with restate.create_test_harness(
                endpoint, restate_image=RESTATE_IMAGE, always_replay=True, disable_retries=True
            ) as harness:
                invocation = asyncio.create_task(harness.client.object_call(run, key=str(session.id), arg=str(turn.id)))
                try:
                    if outcome == "cancelled":
                        with anyio.fail_after(30):
                            while turn.status == "pending":
                                await db.refresh(turn)
                                await anyio.sleep(0.01)
                        await agent_streams.cancel(str(turn.id))
                    assert await invocation == str(turn.id)
                    await db.refresh(turn)
                    if turn.status != outcome:
                        await log_invocation_failures(harness.admin_api_url)
                finally:
                    invocation.cancel()
                    await asyncio.gather(invocation, return_exceptions=True)
            await db.refresh(turn)
            await db.refresh(session)
            await db.refresh(environment)
            checkpoint = session.snapshot_id
            assert turn.status == outcome, turn.error
            assert turn.finished_at is not None
            if outcome == "completed":
                assert len(await store.history(session.id)) >= 2
            else:
                assert turn.error == "AgentRunCancelledError"
                assert await store.active_run(session.id) is None
            assert checkpoint is not None
            if outcome == "completed":
                assert environment.snapshot_id == checkpoint
            else:
                assert environment.snapshot_id is None
            assert await anyio.Path(checkpoint).is_file()
    finally:
        if checkpoint is not None:
            smol = pytest.importorskip("smol")
            await smol.AsyncMachine.delete_checkpoint(checkpoint, smol.ConnectOptions(target="local"))
