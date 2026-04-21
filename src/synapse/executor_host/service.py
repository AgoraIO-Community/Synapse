from __future__ import annotations

import asyncio
import contextlib
import json
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse, urlunparse

import websockets

from synapse.communication.persona_pool import resolve_workspace
from synapse.executor_adapters.acpx import AcpxExecutor, AcpxExecutorSession
from synapse.executor_adapters.codex import CodexExecutor, CodexExecutorSession
from synapse.executor_core import ExecutorEvent, ExecutorEventType, ExecutorSession
from synapse.protocol import (
    CancelRunCommand,
    DispatchRunCommand,
    ExecutorHostExecutor,
    RegisterHostMessage,
    ReleaseRunCommand,
    RunEventMessage,
    SupplyInteractionResponseCommand,
)

from .config import ExecutorHostSettings


@dataclass(slots=True)
class LocalRunContext:
    executor: Any
    execution_session_id: str
    background_task: asyncio.Task[None]


class ExecutorHostService:
    def __init__(
        self,
        *,
        settings: ExecutorHostSettings,
        executors_config: dict[str, Any],
    ) -> None:
        self._settings = settings
        self._executors = self._build_executors(executors_config)
        self._live_sessions: dict[str, ExecutorSession] = {}
        self._active_runs: dict[str, LocalRunContext] = {}
        self._send_lock = asyncio.Lock()

    async def run_forever(self) -> None:
        while True:
            try:
                async with websockets.connect(
                    self._ws_url(),
                    proxy=None,
                    open_timeout=10.0,
                    close_timeout=10.0,
                ) as websocket:
                    await self._send_json(
                        websocket,
                        RegisterHostMessage(
                            host_id=self._settings.host_id,
                            executors=[self._descriptor(name, executor) for name, executor in self._executors.items()],
                        ).model_dump(mode="json"),
                    )
                    await self._recv_json(websocket)
                    while True:
                        payload = await self._recv_json(websocket)
                        await self._handle_message(websocket, payload)
            except asyncio.CancelledError:
                raise
            except Exception:
                await self._cancel_active_runs()
                await asyncio.sleep(1.0)

    async def _handle_message(self, websocket: Any, payload: dict[str, object]) -> None:
        message_type = payload.get("type")
        if message_type == "dispatch_run":
            command = DispatchRunCommand.model_validate(payload)
            await self._dispatch_run(websocket, command)
            return
        if message_type == "cancel_run":
            command = CancelRunCommand.model_validate(payload)
            await self._cancel_run(command)
            return
        if message_type == "supply_interaction_response":
            command = SupplyInteractionResponseCommand.model_validate(payload)
            await self._supply_interaction_response(command)
            return
        if message_type == "release_run":
            command = ReleaseRunCommand.model_validate(payload)
            self._live_sessions.pop(command.execution_session_id, None)
            return

    async def _dispatch_run(self, websocket: Any, command: DispatchRunCommand) -> None:
        executor = self._executors[command.executor_type]
        session = await self._ensure_session(executor, command)
        run_task = asyncio.create_task(self._run_dispatch(websocket, executor, session, command))
        self._active_runs[command.run_id] = LocalRunContext(
            executor=executor,
            execution_session_id=command.execution_session_id,
            background_task=run_task,
        )

    async def _run_dispatch(
        self,
        websocket: Any,
        executor: Any,
        session: ExecutorSession,
        command: DispatchRunCommand,
    ) -> None:
        try:
            from synapse.protocol import ExecutionRun, Task

            run = ExecutionRun(
                run_id=command.run_id,
                task_id=command.task_id,
                execution_session_id=command.execution_session_id,
                executor_type=command.executor_type,
            )
            task = Task(
                task_id=command.task_id,
                root_task_id=command.task_id,
                title=command.title,
                goal=command.goal,
                preferred_executor=command.executor_type,
                session_affinity=command.workspace_id,
                latest_instruction=command.latest_instruction,
                metadata=dict(command.task_metadata),
            )
            async for event in executor.run_task(run, task, session):
                await self._send_json(
                    websocket,
                    RunEventMessage(
                        run_id=command.run_id,
                        execution_session_id=command.execution_session_id,
                        executor_type=command.executor_type,
                        session_id=session.session_id,
                        event_type=event.event_type.value,
                        message=event.message,
                        metadata=dict(event.metadata),
                        latest_resume_handle=_build_resume_handle(executor, session),
                    ).model_dump(mode="json"),
                )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            await self._send_json(
                websocket,
                RunEventMessage(
                    run_id=command.run_id,
                    execution_session_id=command.execution_session_id,
                    executor_type=command.executor_type,
                    session_id=session.session_id,
                    event_type=ExecutorEventType.FAILED.value,
                    message=str(exc),
                    metadata={},
                    latest_resume_handle=_build_resume_handle(executor, session),
                ).model_dump(mode="json"),
            )
        finally:
            self._active_runs.pop(command.run_id, None)
            if not _session_is_alive(session):
                self._live_sessions.pop(command.execution_session_id, None)

    async def _cancel_run(self, command: CancelRunCommand) -> None:
        context = self._active_runs.get(command.run_id)
        if context is None:
            return
        if command.mode == "pause":
            await context.executor.pause_run(command.run_id)
            return
        await context.executor.cancel_run(command.run_id)

    async def _supply_interaction_response(
        self,
        command: SupplyInteractionResponseCommand,
    ) -> None:
        if not isinstance(command.execution_session_id, str) or not command.execution_session_id:
            return
        session = self._live_sessions.get(command.execution_session_id)
        if not isinstance(session, CodexExecutorSession):
            return
        if not isinstance(command.native_response, dict):
            return
        try:
            await session.client.respond_to_request(
                request_id=command.native_response.get("request_id"),
                method=str(command.native_response.get("method") or ""),
                params=dict(command.native_response.get("params") or {}),
                action=command.action,
                answer_text=command.answer_text,
            )
        except Exception:
            return
        session.mark_blocked_resolved()

    async def _ensure_session(self, executor: Any, command: DispatchRunCommand) -> ExecutorSession:
        existing = self._live_sessions.get(command.execution_session_id)
        if existing is not None and _session_is_alive(existing):
            return existing
        workspace_path = str(resolve_workspace(command.workspace_id or command.task_id))
        session = await executor.create_session(workspace_path)
        if command.latest_resume_handle is not None:
            _hydrate_resume_handle(session, command.latest_resume_handle.model_dump(mode="json"))
        self._live_sessions[command.execution_session_id] = session
        return session

    def _build_executors(self, executors_config: dict[str, Any]) -> dict[str, Any]:
        built: dict[str, Any] = {}
        for executor_type in self._settings.enabled_executors:
            config = executors_config.get(executor_type) if isinstance(executors_config, dict) else {}
            if executor_type == "codex":
                built[executor_type] = CodexExecutor(
                    command=str((config or {}).get("command", "codex")),
                    blocked_wait_timeout_seconds=float((config or {}).get("blocked_wait_timeout_seconds", 900.0)),
                )
            elif executor_type == "acpx":
                built[executor_type] = AcpxExecutor(
                    command=str((config or {}).get("command", "acpx")),
                    agent=str((config or {}).get("agent", "codex")),
                    permission_mode=str((config or {}).get("permission_mode", "approve-all")),
                    non_interactive_permissions=str((config or {}).get("non_interactive_permissions", "deny")),
                    timeout_seconds=float((config or {}).get("timeout_seconds"))
                    if (config or {}).get("timeout_seconds") not in (None, "")
                    else None,
                )
        return built

    def _descriptor(self, executor_type: str, executor: Any) -> ExecutorHostExecutor:
        capabilities = executor.get_capabilities()
        return ExecutorHostExecutor(
            executor_type=executor_type,
            supports_resume=capabilities.supports_resume,
            supports_follow_up=capabilities.supports_follow_up,
            supports_pause=capabilities.supports_pause,
            supports_cancel=capabilities.supports_cancel,
        )

    async def _cancel_active_runs(self) -> None:
        contexts = list(self._active_runs.items())
        self._active_runs.clear()
        for run_id, context in contexts:
            context.background_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await context.background_task
            with contextlib.suppress(Exception):
                await context.executor.cancel_run(run_id)

    async def _send_json(self, websocket: Any, payload: dict[str, object]) -> None:
        async with self._send_lock:
            await websocket.send(json.dumps(payload))

    async def _recv_json(self, websocket: Any) -> dict[str, object]:
        raw = await websocket.recv()
        if not isinstance(raw, str):
            raise RuntimeError("Executor host websocket received a non-text payload.")
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise RuntimeError("Executor host websocket received a non-object payload.")
        return payload

    def _ws_url(self) -> str:
        parsed = urlparse(self._settings.synapse_base_url)
        scheme = "wss" if parsed.scheme == "https" else "ws"
        path = parsed.path.rstrip("/") + "/executors/control"
        return urlunparse((scheme, parsed.netloc, path, "", "", ""))


def _session_is_alive(session: ExecutorSession) -> bool:
    if isinstance(session, AcpxExecutorSession):
        return True
    if isinstance(session, CodexExecutorSession):
        return session.is_alive()
    return True


def _hydrate_resume_handle(session: ExecutorSession, resume_handle: dict[str, object]) -> None:
    if isinstance(session, AcpxExecutorSession) and resume_handle.get("executor_id") == "acpx":
        opaque = dict(resume_handle.get("opaque") or {})
        session.hydrate_resume_handle(
            cwd=str(opaque.get("cwd")) if opaque.get("cwd") is not None else None,
            session_name=str(opaque.get("sessionName")) if opaque.get("sessionName") is not None else None,
            agent=str(opaque.get("agent")) if opaque.get("agent") is not None else None,
            acpx_record_id=str(resume_handle.get("session_handle")) if resume_handle.get("session_handle") is not None else None,
            acp_session_id=str(opaque.get("acpSessionId")) if opaque.get("acpSessionId") is not None else None,
            agent_session_id=str(opaque.get("agentSessionId")) if opaque.get("agentSessionId") is not None else None,
        )
        return
    if isinstance(session, CodexExecutorSession) and resume_handle.get("executor_id") == "codex":
        session.thread_id = str(resume_handle.get("session_handle")) if resume_handle.get("session_handle") is not None else None


def _build_resume_handle(executor: Any, session: ExecutorSession):
    if hasattr(executor, "build_resume_handle"):
        try:
            return executor.build_resume_handle(session)
        except Exception:
            return None
    return None
