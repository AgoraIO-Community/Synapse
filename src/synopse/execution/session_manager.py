from __future__ import annotations

from uuid import uuid4

from synopse.blackboard import BlackboardStore
from synopse.executor_adapters.acpx import AcpxExecutorSession
from synopse.executor_adapters.codex import CodexExecutorSession
from synopse.executor_core import Executor, ExecutorSession
from synopse.observability.emitters import ExecutionDiagnosticEmitter
from synopse.observability.reason_codes import (
    EXECUTOR_SESSION_RECREATED,
    EXISTING_LIVE_SESSION_REUSED,
)
from synopse.protocol import AgentResumeHandle, BindingStatus, ExecutionSession, SessionBinding, Task


class SessionManager:
    def __init__(self, *, observability: ExecutionDiagnosticEmitter | None = None) -> None:
        self._live_sessions: dict[str, ExecutorSession] = {}
        self._observability = observability

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
                cached = self._live_sessions.get(existing.execution_session_id)
                if cached is not None and _session_is_alive(cached):
                    active_binding = binding.model_copy(
                        update={"binding_status": BindingStatus.ACTIVE}
                    )
                    await store.put_binding(active_binding)
                    if self._observability is not None:
                        self._observability.session_reused(
                            task_id=task.task_id,
                            execution_session_id=existing.execution_session_id,
                            executor_session_id=cached.session_id,
                            executor_type=cached.executor_type,
                            reason_code=EXISTING_LIVE_SESSION_REUSED,
                        )
                    return existing, active_binding, cached

                executor_session = await executor.create_session(task.session_affinity)
                _hydrate_resume_handle(executor_session, existing.latest_resume_handle)
                self._live_sessions[existing.execution_session_id] = executor_session
                active_binding = binding.model_copy(
                    update={
                        "session_id": executor_session.session_id,
                        "binding_status": BindingStatus.ACTIVE,
                    }
                )
                await store.put_binding(active_binding)
                if self._observability is not None:
                    self._observability.session_reused(
                        task_id=task.task_id,
                        execution_session_id=existing.execution_session_id,
                        executor_session_id=executor_session.session_id,
                        executor_type=executor_session.executor_type,
                        reason_code=EXECUTOR_SESSION_RECREATED,
                    )
                return existing, active_binding, executor_session

        executor_session = await executor.create_session(task.session_affinity)
        execution_session = ExecutionSession(
            execution_session_id=f"exec-session-{uuid4().hex[:8]}",
            task_id=task.task_id,
            base_executor_id=executor.get_capabilities().executor_type,
        )
        self._live_sessions[execution_session.execution_session_id] = executor_session
        updated_binding = binding.model_copy(
            update={
                "execution_session_id": execution_session.execution_session_id,
                "session_id": executor_session.session_id,
                "binding_status": BindingStatus.ACTIVE,
            }
        )
        await store.put_session(execution_session)
        await store.put_binding(updated_binding)
        if self._observability is not None:
            self._observability.session_created(
                task_id=task.task_id,
                execution_session_id=execution_session.execution_session_id,
                executor_session_id=executor_session.session_id,
                executor_type=executor_session.executor_type,
            )
        return execution_session, updated_binding, executor_session

    def drop_live_session(self, execution_session_id: str) -> None:
        self._live_sessions.pop(execution_session_id, None)


def _session_is_alive(session: ExecutorSession) -> bool:
    if isinstance(session, AcpxExecutorSession):
        return True
    if isinstance(session, CodexExecutorSession):
        return session.is_alive()
    return True


def _hydrate_resume_handle(
    session: ExecutorSession,
    resume_handle: AgentResumeHandle | None,
) -> None:
    if (
        isinstance(session, AcpxExecutorSession)
        and resume_handle is not None
        and resume_handle.executor_id == "acpx"
    ):
        opaque = resume_handle.opaque
        session.hydrate_resume_handle(
            cwd=str(opaque.get("cwd")) if opaque.get("cwd") is not None else None,
            session_name=(
                str(opaque.get("sessionName")) if opaque.get("sessionName") is not None else None
            ),
            agent=str(opaque.get("agent")) if opaque.get("agent") is not None else None,
            acpx_record_id=resume_handle.session_handle,
            acp_session_id=(
                str(opaque.get("acpSessionId")) if opaque.get("acpSessionId") is not None else None
            ),
            agent_session_id=(
                str(opaque.get("agentSessionId"))
                if opaque.get("agentSessionId") is not None
                else None
            ),
        )
        return
    if (
        isinstance(session, CodexExecutorSession)
        and resume_handle is not None
        and resume_handle.executor_id == "codex"
    ):
        session.thread_id = resume_handle.session_handle
