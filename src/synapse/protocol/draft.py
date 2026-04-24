from __future__ import annotations

from enum import StrEnum
from pydantic import BaseModel, Field


class DraftRiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class DraftSessionStatus(StrEnum):
    EMPTY = "empty"
    LISTENING = "listening"
    DRAFTING = "drafting"
    READY = "ready"
    SENT = "sent"
    CLEARED = "cleared"


class AsrTurn(BaseModel):
    id: str
    raw_text: str
    normalized_text: str | None = None
    confidence: float | None = None
    started_at: str
    ended_at: str


class Draft(BaseModel):
    title: str
    goal: str
    constraints: list[str] = Field(default_factory=list)
    acceptance_criteria: list[str] = Field(default_factory=list)
    canonical_instruction: str
    assumptions: list[str] = Field(default_factory=list)
    missing_info: list[str] = Field(default_factory=list)
    last_update_summary: str = ""
    confidence: float = 0.5
    risk_level: DraftRiskLevel = DraftRiskLevel.MEDIUM


class DraftSnapshot(BaseModel):
    id: str
    draft: Draft
    source_asr_turn_ids: list[str] = Field(default_factory=list)
    created_at: str


class DraftSession(BaseModel):
    id: str
    assigned_bro_id: str
    asr_turns: list[AsrTurn] = Field(default_factory=list)
    current_draft: Draft | None = None
    snapshots: list[DraftSnapshot] = Field(default_factory=list)
    status: DraftSessionStatus = DraftSessionStatus.EMPTY
    created_at: str
    updated_at: str
