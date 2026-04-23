"""User-defined persona model.

Each persona is a named worker that can be assigned to one task at a time.
Personas are created by the user before task execution and persist across sessions.
"""

from __future__ import annotations

from pydantic import BaseModel


class Persona(BaseModel):
    persona_id: str
    name: str
    avatar: str = ""
    base_prompt: str = ""
    executor_node_id: str | None = None
    status: str = "idle"  # "idle" | "busy"
    current_task_id: str | None = None
