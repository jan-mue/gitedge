"""Normalized agent conversations and Agent Trace attribution records."""

import uuid
from datetime import datetime

from sqlalchemy import JSON, UUID, CheckConstraint, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.entities.base import Base


class AgentEnvironment(Base):
    """Repository collection and reusable setup image owned by one user."""

    __tablename__ = "agent_environment"
    user_id: Mapped[uuid.UUID] = mapped_column(UUID, ForeignKey("user.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    snapshot_id: Mapped[str | None] = mapped_column(Text)
    setup_script: Mapped[str] = mapped_column(Text, default="")
    instructions: Mapped[str] = mapped_column(Text, default="")


class AgentEnvironmentRepository(Base):
    """Ordered, authorized repository membership of an environment."""

    __tablename__ = "agent_environment_repository"
    __table_args__ = (UniqueConstraint("environment_id", "repository_id"),)
    environment_id: Mapped[uuid.UUID] = mapped_column(UUID, ForeignKey("agent_environment.id", ondelete="CASCADE"))
    repository_id: Mapped[uuid.UUID] = mapped_column(UUID, ForeignKey("repository.id", ondelete="CASCADE"))
    revision: Mapped[str | None] = mapped_column(String(100))


class AgentSession(Base):
    """A setup or coding conversation with its own forked sandbox image."""

    __tablename__ = "agent_session"
    environment_id: Mapped[uuid.UUID] = mapped_column(
        UUID, ForeignKey("agent_environment.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID, ForeignKey("user.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    kind: Mapped[str] = mapped_column(String(20), default="coding")
    snapshot_id: Mapped[str | None] = mapped_column(Text)


class AgentRun(Base):
    """One durable turn, with a stable invocation and terminal notification state."""

    __tablename__ = "agent_run"
    __table_args__ = (UniqueConstraint("session_id", "request_id"),)
    session_id: Mapped[uuid.UUID] = mapped_column(UUID, ForeignKey("agent_session.id", ondelete="CASCADE"), index=True)
    request_id: Mapped[str] = mapped_column(String(100))
    model: Mapped[str] = mapped_column(String(250))
    prompt: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    invocation_id: Mapped[str | None] = mapped_column(Text)
    error: Mapped[str | None] = mapped_column(Text)
    notification_read: Mapped[bool] = mapped_column(default=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AgentMessage(Base):
    """Individual model messages, preserving typed PydanticAI parts for continuation."""

    __tablename__ = "agent_message"
    __table_args__ = (UniqueConstraint("run_id", "position"),)
    run_id: Mapped[uuid.UUID] = mapped_column(UUID, ForeignKey("agent_run.id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column(Integer)
    role: Mapped[str] = mapped_column(String(20))
    parts: Mapped[list[dict]] = mapped_column(JSON)


class AgentTrace(Base):
    """Agent Trace record header; files and attributed ranges are separate rows."""

    __tablename__ = "agent_trace"
    run_id: Mapped[uuid.UUID] = mapped_column(UUID, ForeignKey("agent_run.id", ondelete="CASCADE"), index=True)
    repository_id: Mapped[uuid.UUID] = mapped_column(UUID, ForeignKey("repository.id", ondelete="CASCADE"))
    version: Mapped[str] = mapped_column(String(20), default="0.1.0")
    vcs_type: Mapped[str] = mapped_column(String(20), default="git")
    revision: Mapped[str] = mapped_column(String(100))
    tool_name: Mapped[str] = mapped_column(String(100), default="gitedge")
    tool_version: Mapped[str] = mapped_column(String(30), default="0.1.0")


class AgentTraceRange(Base):
    """Per-file, per-conversation attribution, compatible with Agent Trace ranges."""

    __tablename__ = "agent_trace_range"
    __table_args__ = (CheckConstraint("start_line >= 1 AND end_line >= start_line", name="valid_lines"),)
    trace_id: Mapped[uuid.UUID] = mapped_column(UUID, ForeignKey("agent_trace.id", ondelete="CASCADE"), index=True)
    session_id: Mapped[uuid.UUID] = mapped_column(UUID, ForeignKey("agent_session.id", ondelete="CASCADE"))
    path: Mapped[str] = mapped_column(Text)
    start_line: Mapped[int] = mapped_column(Integer)
    end_line: Mapped[int] = mapped_column(Integer)
    contributor_type: Mapped[str] = mapped_column(String(20), default="ai")
    model_id: Mapped[str | None] = mapped_column(String(250))
    content_hash: Mapped[str | None] = mapped_column(String(200))
    conversation_url: Mapped[str | None] = mapped_column(Text)
