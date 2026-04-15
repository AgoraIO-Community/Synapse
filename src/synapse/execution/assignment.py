from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from synapse.blackboard import BlackboardStore
from synapse.observability.emitters.execution import ExecutionDiagnosticEmitter
from synapse.blackboard.revisions import claim_is_active
from synapse.protocol import BindingStatus, SessionBinding, Task


class AssignmentManager:
    def __init__(
        self,
        worker_id: str,
        *,
        lease_seconds: int = 300,
        observability: ExecutionDiagnosticEmitter | None = None,
    ) -> None:
        self._worker_id = worker_id
        self._lease_seconds = lease_seconds
        self._observability = observability

    async def claim_task(self, store: BlackboardStore, task: Task) -> SessionBinding | None:
        binding = await store.get_binding(task.task_id)
        if binding is not None and claim_is_active(binding) and binding.claimed_by not in {
            None,
            self._worker_id,
        }:
            return None

        expires_at = datetime.now(UTC) + timedelta(seconds=self._lease_seconds)
        claimed = SessionBinding(
            task_id=task.task_id,
            execution_session_id=binding.execution_session_id if binding else None,
            session_id=binding.session_id if binding else None,
            claimed_by=self._worker_id,
            claim_expires_at=expires_at.isoformat(),
            execution_revision=task.task_revision,
            binding_status=BindingStatus.CLAIMED,
        )
        await store.put_binding(claimed)
        if self._observability is not None:
            self._observability.task_claimed(
                task_id=task.task_id,
                execution_session_id=claimed.execution_session_id,
                worker_id=self._worker_id,
            )
        return claimed

    @property
    def worker_id(self) -> str:
        return self._worker_id
