from __future__ import annotations

from dataclasses import dataclass, field
from uuid import uuid4

from synapse.communication.model import CommunicationModel

from .config import Settings
from .executor_node_manager import ExecutorNodeManager
from .session import SessionRuntime, create_session_runtime


@dataclass(slots=True)
class RuntimeContainer:
    communication_model: CommunicationModel
    settings: Settings
    executor_node_manager: ExecutorNodeManager = field(init=False)
    _sessions: dict[str, SessionRuntime] = field(default_factory=dict, init=False)

    def __post_init__(self) -> None:
        self.executor_node_manager = ExecutorNodeManager(
            detached_executor_types=self.settings.detached_executor_types,
        )

    def create_session(self) -> SessionRuntime:
        session_id = f"session-{uuid4().hex[:8]}"
        session = create_session_runtime(
            session_id,
            model=self.communication_model,
            settings=self.settings,
            executor_node_manager=self.executor_node_manager,
        )
        self._sessions[session_id] = session
        return session

    def get_session(self, session_id: str) -> SessionRuntime:
        try:
            return self._sessions[session_id]
        except KeyError as exc:
            raise KeyError(f"Unknown session: {session_id}") from exc

    async def handle_executor_node_connected(self) -> list[str]:
        available = {
            executor_type
            for executor_type in self.executor_node_manager.detached_executor_types
            if self.executor_node_manager.is_executor_connected(executor_type)
        }
        updated_task_ids: list[str] = []
        for session in self._sessions.values():
            changed = await session.requeue_waiting_executor_tasks(available)
            if changed:
                session.schedule_execution()
                updated_task_ids.extend(changed)
        return updated_task_ids
