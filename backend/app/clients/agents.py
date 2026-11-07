"""SQL stores for agent workspace metadata and conversation history."""

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.clients.database import SQLStore
from app.entities.agents import (
    AgentEnvironment,
    AgentEnvironmentRepository,
    AgentMessage,
    AgentRun,
    AgentSession,
    AgentTrace,
    AgentTraceRange,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.clients.agent_traces import RepositoryTrace


class AgentStore(SQLStore[AgentSession]):
    """Keep queries and atomic workspace writes outside the service layer."""

    def __init__(self, db: AsyncSession) -> None:
        """Use the request or durable invocation's database session."""
        super().__init__(db, AgentSession)

    async def environments(self, user_id: uuid.UUID) -> list[AgentEnvironment]:
        """List only environments owned by the authenticated user."""
        return list(await self.db.scalars(select(AgentEnvironment).where(AgentEnvironment.user_id == user_id)))

    async def environment(self, environment_id: uuid.UUID) -> AgentEnvironment | None:
        """Find an environment without treating IDs as authorization."""
        return await self.db.get(AgentEnvironment, environment_id)

    async def create_environment(self, environment: AgentEnvironment, repositories: list[uuid.UUID]) -> None:
        """Persist a collection and its members atomically."""
        self.db.add(environment)
        self.db.add_all(
            [AgentEnvironmentRepository(environment_id=environment.id, repository_id=repo) for repo in repositories]
        )
        await self.db.commit()
        await self.db.refresh(environment)

    async def repositories(self, environment_id: uuid.UUID) -> list[uuid.UUID]:
        """Read members for permission rechecks before each run."""
        return list(
            await self.db.scalars(
                select(AgentEnvironmentRepository.repository_id).where(
                    AgentEnvironmentRepository.environment_id == environment_id
                )
            )
        )

    async def sessions(self, user_id: uuid.UUID) -> list[AgentSession]:
        """List owned conversations in recency order."""
        return list(
            await self.db.scalars(
                select(AgentSession).where(AgentSession.user_id == user_id).order_by(AgentSession.updated_at.desc())
            )
        )

    async def run(self, run_id: uuid.UUID) -> AgentRun | None:
        """Find a turn for authorized streaming and durable execution."""
        return await self.db.get(AgentRun, run_id)

    async def request(self, session_id: uuid.UUID, request_id: str) -> AgentRun | None:
        """Find an earlier idempotent submission."""
        return await self.db.scalar(
            select(AgentRun).where(AgentRun.session_id == session_id, AgentRun.request_id == request_id)
        )

    async def create_run(self, turn: AgentRun) -> AgentRun:
        """Atomically deduplicate concurrent submissions by conversation/request ID."""
        await self.db.execute(
            insert(AgentRun)
            .values(
                id=turn.id,
                session_id=turn.session_id,
                request_id=turn.request_id,
                prompt=turn.prompt,
                model=turn.model,
                status="pending",
            )
            .on_conflict_do_nothing(index_elements=[AgentRun.session_id, AgentRun.request_id])
        )
        await self.db.commit()
        stored = await self.request(turn.session_id, turn.request_id)
        if stored is None:
            raise RuntimeError("Turn submission was not persisted")
        return stored

    async def save_run(self, run: AgentRun) -> None:
        """Commit a turn state transition."""
        self.db.add(run)
        await self.db.commit()

    async def history(self, session_id: uuid.UUID) -> list[dict]:
        """Read individual messages in turn order for model continuation."""
        messages = await self.db.scalars(
            select(AgentMessage)
            .join(AgentRun, AgentRun.id == AgentMessage.run_id)
            .where(AgentRun.session_id == session_id)
            .order_by(AgentRun.created_at, AgentMessage.position)
        )
        return [{"kind": message.role, "parts": message.parts} for message in messages]

    async def finish(
        self, run: AgentRun, session: AgentSession, snapshot: str, messages: list[dict], traces: list[RepositoryTrace]
    ) -> None:
        """Commit conversation, latest image, and successful terminal state together."""
        session.snapshot_id = snapshot
        run.status = "completed"
        run.finished_at = datetime.now(UTC)
        for item in traces:
            trace = AgentTrace(
                id=uuid.uuid4(),
                run_id=run.id,
                repository_id=uuid.UUID(item["repository_id"]),
                revision=item["revision"],
            )
            self.db.add(trace)
            self.db.add_all(
                [
                    AgentTraceRange(
                        trace_id=trace.id,
                        session_id=session.id,
                        model_id=run.model.replace(":", "/", 1),
                        conversation_url=f"/agents?session={session.id}",
                        **file,
                    )
                    for file in item["files"]
                ]
            )
        self.db.add_all(
            [
                AgentMessage(run_id=run.id, position=index, role=message["kind"], parts=message["parts"])
                for index, message in enumerate(messages)
            ]
        )
        if session.kind == "setup":
            environment = await self.environment(session.environment_id)
            if environment is not None:
                environment.snapshot_id = snapshot
        await self.db.commit()

    async def fail(self, run: AgentRun, message: str) -> None:
        """Persist terminal failure for workspace notifications."""
        run.status = "failed"
        run.error = message
        run.finished_at = datetime.now(UTC)
        await self.db.commit()

    async def notifications(self, user_id: uuid.UUID) -> list[AgentRun]:
        """Return completed and failed turns only to their session owner."""
        return list(
            await self.db.scalars(
                select(AgentRun)
                .join(AgentSession)
                .where(
                    AgentSession.user_id == user_id,
                    AgentRun.status.in_(["completed", "failed"]),
                    AgentRun.notification_read.is_(False),
                )
                .order_by(AgentRun.finished_at.desc())
                .limit(50)
            )
        )
