from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

from synapse.executor_core import ExecutorEvent, ExecutorEventType
from synapse.protocol import (
    AckMessage,
    CancelRunCommand,
    DispatchRunCommand,
    ExecutorHostExecutor,
    InteractionRequest,
    RegisterHostMessage,
    RunEventMessage,
    SupplyInteractionResponseCommand,
)


@dataclass(slots=True)
class HostRunEnvelope:
    event: ExecutorEvent
    latest_resume_handle: dict[str, object] | None = None


@dataclass(slots=True)
class RunDispatchState:
    run_id: str
    execution_session_id: str
    executor_type: str


@dataclass(slots=True)
class HostConnectionState:
    host_id: str | None = None
    metadata: dict[str, object] = field(default_factory=dict)
    executors: dict[str, ExecutorHostExecutor] = field(default_factory=dict)
    connected: bool = False


class ExecutorHostAuthError(RuntimeError):
    pass


class ExecutorHostManager:
    def __init__(
        self,
        *,
        detached_executor_types: tuple[str, ...],
    ) -> None:
        self._detached_executor_types = detached_executor_types
        self._connection: Any = None
        self._connection_state = HostConnectionState()
        self._send_lock = asyncio.Lock()
        self._run_queues: dict[str, asyncio.Queue[HostRunEnvelope]] = {}
        self._run_states: dict[str, RunDispatchState] = {}

    @property
    def detached_executor_types(self) -> tuple[str, ...]:
        return self._detached_executor_types

    @property
    def host_id(self) -> str | None:
        return self._connection_state.host_id

    @property
    def connected(self) -> bool:
        return self._connection_state.connected

    def is_detached_executor(self, executor_type: str) -> bool:
        return executor_type in self._detached_executor_types

    def is_executor_connected(self, executor_type: str) -> bool:
        return self.connected and executor_type in self._connection_state.executors

    def executor_availability(self, executor_type: str) -> dict[str, object]:
        if not self.is_detached_executor(executor_type):
            return {
                "connected": True,
                "host_id": None,
                "availability_reason": None,
            }
        if self.is_executor_connected(executor_type):
            return {
                "connected": True,
                "host_id": self._connection_state.host_id,
                "availability_reason": None,
            }
        reason = "host_disconnected"
        if self.connected and executor_type not in self._connection_state.executors:
            reason = "host_missing_executor"
        return {
            "connected": False,
            "host_id": self.host_id,
            "availability_reason": reason,
        }

    async def register_connection(self, websocket: Any, register: RegisterHostMessage) -> AckMessage:
        if self._connection is not None and self._connection is not websocket and self.connected:
            raise ExecutorHostAuthError("An executor host is already connected.")
        self._connection = websocket
        self._connection_state = HostConnectionState(
            host_id=register.host_id,
            metadata=dict(register.metadata),
            executors={executor.executor_type: executor for executor in register.executors},
            connected=True,
        )
        return AckMessage(message_type=register.type, detail="registered")

    async def disconnect(self, *, reason: str) -> None:
        self._connection = None
        host_id = self._connection_state.host_id
        self._connection_state = HostConnectionState(host_id=host_id, connected=False)
        for run_id, queue in list(self._run_queues.items()):
            state = self._run_states.get(run_id)
            if state is None:
                continue
            await queue.put(
                HostRunEnvelope(
                    event=ExecutorEvent(
                        run_id=run_id,
                        session_id=state.execution_session_id,
                        event_type=ExecutorEventType.WAITING_EXECUTOR,
                        message=(
                            f"Waiting for executor host '{host_id}' to reconnect."
                            if host_id
                            else "Waiting for detached executor host to reconnect."
                        ),
                        metadata={
                            "executor_host_id": host_id,
                            "availability_reason": reason,
                        },
                    )
                )
            )

    async def dispatch_run(
        self,
        *,
        run_id: str,
        execution_session_id: str,
        executor_type: str,
        task_id: str,
        title: str,
        goal: str,
        latest_instruction: str | None,
        workspace_id: str | None,
        task_metadata: dict[str, object],
        latest_resume_handle: dict[str, object] | None,
    ) -> asyncio.Queue[HostRunEnvelope]:
        queue: asyncio.Queue[HostRunEnvelope] = asyncio.Queue()
        self._run_queues[run_id] = queue
        self._run_states[run_id] = RunDispatchState(
            run_id=run_id,
            execution_session_id=execution_session_id,
            executor_type=executor_type,
        )
        if not self.is_executor_connected(executor_type):
            host_label = self.host_id or "detached executor host"
            await queue.put(
                HostRunEnvelope(
                    event=ExecutorEvent(
                        run_id=run_id,
                        session_id=execution_session_id,
                        event_type=ExecutorEventType.WAITING_EXECUTOR,
                        message=f"Waiting for {host_label} to connect.",
                        metadata={
                            "executor_host_id": self.host_id,
                            "availability_reason": self.executor_availability(executor_type)["availability_reason"],
                        },
                    )
                )
            )
            return queue

        command = DispatchRunCommand(
            run_id=run_id,
            execution_session_id=execution_session_id,
            executor_type=executor_type,
            task_id=task_id,
            title=title,
            goal=goal,
            latest_instruction=latest_instruction,
            workspace_id=workspace_id,
            task_metadata=task_metadata,
            latest_resume_handle=latest_resume_handle,
        )
        try:
            await self._send_json(command.model_dump(mode="json"))
        except Exception:
            await self.disconnect(reason="dispatch_failed")
        return queue

    async def cancel_run(self, run_id: str, *, mode: str = "cancel") -> None:
        state = self._run_states.get(run_id)
        if state is None or self._connection is None or not self.connected:
            return
        command = CancelRunCommand(
            run_id=run_id,
            execution_session_id=state.execution_session_id,
            mode="pause" if mode == "pause" else "cancel",
        )
        try:
            await self._send_json(command.model_dump(mode="json"))
        except Exception:
            await self.disconnect(reason="cancel_failed")

    async def supply_interaction_response(
        self,
        request: InteractionRequest,
        *,
        action: str,
        answer_text: str | None,
    ) -> bool:
        native_response = request.opaque.get("native_response")
        if not isinstance(native_response, dict):
            return False
        if self._connection is None or not self.connected:
            return False
        command = SupplyInteractionResponseCommand(
            interaction_request_id=request.request_id,
            execution_session_id=request.execution_session_id,
            run_id=request.run_id,
            action=action,
            answer_text=answer_text,
            native_response=native_response,
        )
        try:
            await self._send_json(command.model_dump(mode="json"))
        except Exception:
            await self.disconnect(reason="interaction_response_failed")
            return False
        return True

    async def publish_run_event(self, message: RunEventMessage) -> AckMessage:
        queue = self._run_queues.get(message.run_id)
        if queue is None:
            return AckMessage(message_type=message.type, run_id=message.run_id, ok=False, detail="unknown_run")
        latest_resume_handle = (
            message.latest_resume_handle.model_dump(mode="json")
            if message.latest_resume_handle is not None
            else None
        )
        await queue.put(
            HostRunEnvelope(
                event=ExecutorEvent(
                    run_id=message.run_id,
                    session_id=message.session_id,
                    event_type=ExecutorEventType(message.event_type),
                    message=message.message,
                    metadata=dict(message.metadata),
                ),
                latest_resume_handle=latest_resume_handle,
            )
        )
        return AckMessage(message_type=message.type, run_id=message.run_id, detail="queued")

    def finish_run(self, run_id: str) -> None:
        self._run_queues.pop(run_id, None)
        self._run_states.pop(run_id, None)

    async def _send_json(self, payload: dict[str, object]) -> None:
        websocket = self._connection
        if websocket is None:
            raise RuntimeError("No executor host websocket is connected.")
        async with self._send_lock:
            await websocket.send_json(payload)
