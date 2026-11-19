import uuid
from typing import TYPE_CHECKING

import anyio
import pytest
from fastapi import FastAPI
from sqlalchemy import select

from app.agents.runtime import restate_app, run
from app.api.dependencies import get_coding_agent_deps
from app.api.restate import RestateDependencies
from app.clients.agent_credentials import AgentCredentialStore
from app.clients.agents import AgentStore
from app.clients.database import create_db_engine, create_session_factory
from app.config import settings
from app.entities.agents import AgentEnvironment, AgentRun, AgentSession
from app.entities.users import User
from tests.integration.agents.containers import OLLAMA_MODEL
from tests.integration.agents.harness import agent_harness

if TYPE_CHECKING:
    from pathlib import Path

    from pydantic_ai_harness.smol_sandbox import SmolSandbox
    from testcontainers.community.ollama import OllamaContainer

    from app.clients.agent_streams import AgentStreamStore
    from app.clients.blob_storage import S3Client


@pytest.mark.usefixtures("infrastructure")
async def test_completed_turn_replays_after_sandbox_cleanup(
    agent_ollama: OllamaContainer,
    agent_streams: AgentStreamStore,
    agent_blobs: S3Client,
    agent_sandbox_capability: SmolSandbox,
    tmp_path: Path,
) -> None:
    original_endpoints = settings.AGENTS_OPENAI_ENDPOINTS
    original_checkpoints = settings.AGENTS_SMOL_CHECKPOINT_DIR
    settings.AGENTS_OPENAI_ENDPOINTS = {"ollama": f"{agent_ollama.get_endpoint()}/v1"}
    settings.AGENTS_SMOL_CHECKPOINT_DIR = tmp_path
    checkpoint = None
    try:
        async with create_db_engine() as engine, create_session_factory(engine)() as db:
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
            deps = get_coding_agent_deps(agent_streams, agent_blobs, agent_sandbox_capability)
            app = FastAPI()
            app.dependency_overrides[get_coding_agent_deps] = lambda: deps
            app.add_middleware(RestateDependencies, dependency_overrides_provider=app)
            app.mount("/restate", restate_app())
            # The harness forces journal replay at each step, including after VM deletion.
            async with agent_harness(app, disable_retries=True, mount_path="/restate") as harness:
                assert await harness.client.object_call(run, key=str(session.id), arg=str(turn.id)) == str(turn.id)
            await db.refresh(turn)
            await db.refresh(session)
            await db.refresh(environment)
            assert turn.status == "completed", turn.error
            assert turn.finished_at is not None
            assert len(await store.history(session.id)) >= 2
            checkpoint = session.snapshot_id
            assert checkpoint is not None
            assert environment.snapshot_id == checkpoint
            assert await anyio.Path(checkpoint).is_file()
    finally:
        settings.AGENTS_OPENAI_ENDPOINTS = original_endpoints
        settings.AGENTS_SMOL_CHECKPOINT_DIR = original_checkpoints
        if checkpoint is not None:
            from smol import AsyncMachine, ConnectOptions  # noqa: PLC0415 - optional host virtualization

            await AsyncMachine.delete_checkpoint(checkpoint, ConnectOptions(target="local"))
