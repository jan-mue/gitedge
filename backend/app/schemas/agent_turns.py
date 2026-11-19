"""Internal contracts for private Restate agent execution."""

import uuid

from pydantic import BaseModel, Field
from pydantic_ai.workspaces import WorkspaceRef


class AgentTurnRequest(BaseModel):
    """Immutable input passed by the authorized conversation orchestrator."""

    run_id: str
    session_id: str
    user_id: uuid.UUID
    prompt: str
    model: str
    instructions: str
    history: list[dict] = Field(default_factory=list)
    workspace: WorkspaceRef
