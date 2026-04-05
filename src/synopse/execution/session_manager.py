from __future__ import annotations

from uuid import uuid4

from synopse.blackboard import BlackboardStore
from synopse.executor_core import Executor, ExecutorSession
from synopse.protocol import BindingStatus, ExecutionSession, SessionBinding, Task


class SessionManager:
    async def ensure_session(
        self,
        store: BlackboardStore,
        executor: Executor,
        task: Task,
        binding: SessionBinding,
    ) -> tuple[ExecutionSession, SessionBinding, ExecutorSession]:
        if binding.execution_session_id:
            existing = await store.get_session(binding.execution_session_id)
            if existing is not None:
                active_binding = binding.model_copy(
                    update={"binding_status": BindingStatus.ACTIVE}
                )
                await store.put_binding(active_binding)
                executor_session = ExecutorSession(
                    session_id=active_binding.session_id or f"missing-{uuid4().hex[:8]}",
                    executor_type=executor.get_capabilities().executor_type,
                )
                return existing, active_binding, executor_session

        executor_session = await executor.create_session(task.session_affinity)
        execution_session = ExecutionSession(
            execution_session_id=f"exec-session-{uuid4().hex[:8]}",
            task_id=task.task_id,
            base_executor_id=executor.get_capabilities().executor_type,
        )
        updated_binding = binding.model_copy(
            update={
                "execution_session_id": execution_session.execution_session_id,
                "session_id": executor_session.session_id,
                "binding_status": BindingStatus.ACTIVE,
            }
        )
        await store.put_session(execution_session)
        await store.put_binding(updated_binding)
        return execution_session, updated_binding, executor_session
