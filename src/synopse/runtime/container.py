from __future__ import annotations

from dataclasses import dataclass, field
from uuid import uuid4

from synopse.communication.model import CommunicationModel

from .session import SessionRuntime, create_session_runtime


@dataclass(slots=True)
class RuntimeContainer:
    communication_model: CommunicationModel
    _sessions: dict[str, SessionRuntime] = field(default_factory=dict, init=False)

    def create_session(self) -> SessionRuntime:
        session_id = f"session-{uuid4().hex[:8]}"
        session = create_session_runtime(session_id, model=self.communication_model)
        self._sessions[session_id] = session
        return session

    def get_session(self, session_id: str) -> SessionRuntime:
        try:
            return self._sessions[session_id]
        except KeyError as exc:
            raise KeyError(f"Unknown session: {session_id}") from exc
