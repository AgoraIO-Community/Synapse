from __future__ import annotations

from runtime.llm.fallback import heuristic_interpretation
from runtime.protocols.runtime import ActionBundle, RoutingDecision
from runtime.protocols.stream import SessionSnapshot


class InterpreterClient:
    def interpret(
        self, *, message_id: str, text: str, snapshot: SessionSnapshot
    ) -> tuple[RoutingDecision, ActionBundle]:
        return heuristic_interpretation(
            message_id=message_id,
            text=text,
            has_existing_tasks=bool(snapshot.task_registry),
        )
