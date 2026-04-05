from __future__ import annotations

from pydantic import BaseModel, Field

from synopse.protocol import AgentResumeHandle, RunStatus


class ExecutorResult(BaseModel):
    status: RunStatus
    summary: str | None = None
    resume_handle: AgentResumeHandle | None = None
    metadata: dict[str, object] = Field(default_factory=dict)
