from __future__ import annotations

import asyncio
import os
from pathlib import Path
from uuid import uuid4

from synopse.executor_core import (
    ExecutorCapabilities,
    ExecutorEvent,
    ExecutorEventType,
)
from synopse.protocol import AgentResumeHandle, ExecutionRun, Task

from .client import CodexAppServerClient
from .jsonrpc import JsonRpcPeer
from .session import CodexExecutorSession


class CodexExecutor:
    def __init__(self, *, command: str = "codex") -> None:
        self._command = command
        self._capabilities = ExecutorCapabilities(
            executor_type="codex",
            supports_resume=True,
            supports_follow_up=True,
            supports_pause=False,
            supports_cancel=True,
            supports_setup=False,
        )
        self._active_runs: dict[str, CodexExecutorSession] = {}

    def get_capabilities(self) -> ExecutorCapabilities:
        return self._capabilities

    async def create_session(self, workspace_id: str | None = None) -> CodexExecutorSession:
        cwd = Path(workspace_id or os.getcwd()).resolve()
        process = await asyncio.create_subprocess_exec(
            self._command,
            "app-server",
            cwd=str(cwd),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        if process.stdin is None or process.stdout is None:
            raise RuntimeError("Codex app-server did not expose stdio pipes.")
        peer = JsonRpcPeer(process.stdout, process.stdin)
        client = CodexAppServerClient(peer)
        session = CodexExecutorSession(
            session_id=f"codex-session-{uuid4().hex[:8]}",
            executor_type="codex",
            metadata={"cwd": str(cwd)},
        )
        session.attach(process=process, peer=peer, client=client, cwd=cwd)
        await client.initialize()
        account = await client.get_account()
        if account.get("requiresOpenaiAuth") and account.get("account") is None:
            await session.close()
            raise RuntimeError("Codex authentication required.")
        return session

    async def cancel_run(self, run_id: str) -> None:
        session = self._active_runs.pop(run_id, None)
        if session is not None:
            await session.close()

    async def pause_run(self, run_id: str) -> None:
        return None

    async def run_task(
        self,
        run: ExecutionRun,
        task: Task,
        session: CodexExecutorSession,
    ):
        self._active_runs[run.run_id] = session
        try:
            prompt = self._build_prompt(task)
            thread_id = await self._ensure_thread(session)
            turn = await session.client.turn_start(thread_id=thread_id, prompt=prompt)
            turn_id = _get_nested(turn, "turn", "id")
            if not isinstance(turn_id, str):
                raise RuntimeError("Codex turn/start did not return a turn id.")

            last_assistant_message: str | None = None
            while True:
                event = await session.client.next_event()
                method = str(event.get("method", ""))
                params = event.get("params")
                if not isinstance(params, dict):
                    continue

                if method == "turn/completed":
                    completed_turn = params.get("turn")
                    if isinstance(completed_turn, dict) and completed_turn.get("id") != turn_id:
                        continue
                    status = _get_nested(params, "turn", "status")
                    if status == "completed":
                        if not last_assistant_message:
                            last_assistant_message = await self._read_final_assistant_message(
                                session,
                                turn_id,
                            )
                        yield ExecutorEvent(
                            run_id=run.run_id,
                            session_id=session.session_id,
                            event_type=ExecutorEventType.COMPLETED,
                            message=last_assistant_message or f"Completed: {task.title}",
                            metadata={"thread_id": session.thread_id or ""},
                        )
                        return
                    error_message = _get_nested(params, "turn", "error", "message")
                    yield ExecutorEvent(
                        run_id=run.run_id,
                        session_id=session.session_id,
                        event_type=ExecutorEventType.FAILED,
                        message=str(error_message or "Codex turn failed."),
                        metadata={"thread_id": session.thread_id or ""},
                    )
                    return

                if method == "error":
                    message = _get_nested(params, "error", "message")
                    will_retry = params.get("willRetry")
                    if will_retry:
                        yield ExecutorEvent(
                            run_id=run.run_id,
                            session_id=session.session_id,
                            event_type=ExecutorEventType.PROGRESS,
                            message=str(message or "Codex retrying."),
                            metadata={"thread_id": session.thread_id or ""},
                        )
                    continue

                if method in {"item/started", "item/completed"}:
                    item = params.get("item")
                    if isinstance(item, dict):
                        item_type = item.get("type")
                        if item_type in {"assistantMessage", "agentMessage"}:
                            extracted = _extract_item_text(item)
                            if extracted:
                                last_assistant_message = extracted
                                yield ExecutorEvent(
                                    run_id=run.run_id,
                                    session_id=session.session_id,
                                    event_type=ExecutorEventType.PROGRESS,
                                    message=extracted,
                                    metadata={"thread_id": session.thread_id or ""},
                                )
                                continue
                        if item_type not in {None, "userMessage"}:
                            yield ExecutorEvent(
                                run_id=run.run_id,
                                session_id=session.session_id,
                                event_type=ExecutorEventType.PROGRESS,
                                message=f"Codex {method.replace('/', ' ')}: {item_type}",
                                metadata={"thread_id": session.thread_id or ""},
                            )
                    continue

                if "user_input" in method.lower() or "request" in method.lower() and "question" in method.lower():
                    question_text = _extract_question_text(params)
                    yield ExecutorEvent(
                        run_id=run.run_id,
                        session_id=session.session_id,
                        event_type=ExecutorEventType.BLOCKED,
                        message=question_text or "Codex is waiting for user input.",
                        metadata={"thread_id": session.thread_id or ""},
                    )
                    return

                if method == "thread/status/changed":
                    status_type = _get_nested(params, "status", "type")
                    if status_type == "systemError":
                        yield ExecutorEvent(
                            run_id=run.run_id,
                            session_id=session.session_id,
                            event_type=ExecutorEventType.FAILED,
                            message="Codex thread entered systemError state.",
                            metadata={"thread_id": session.thread_id or ""},
                        )
                        return
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            yield ExecutorEvent(
                run_id=run.run_id,
                session_id=session.session_id,
                event_type=ExecutorEventType.FAILED,
                message=str(exc),
                metadata={"stderr": session.stderr_text()},
            )
        finally:
            self._active_runs.pop(run.run_id, None)

    async def _ensure_thread(self, session: CodexExecutorSession) -> str:
        if session.thread_id:
            try:
                result = await session.client.thread_fork(
                    thread_id=session.thread_id,
                    cwd=str(session.cwd),
                )
            except Exception:
                result = await session.client.thread_start(cwd=str(session.cwd))
        else:
            result = await session.client.thread_start(cwd=str(session.cwd))
        thread_id = _get_nested(result, "thread", "id")
        if not isinstance(thread_id, str):
            raise RuntimeError("Codex did not return a thread id.")
        session.thread_id = thread_id
        return thread_id

    def build_resume_handle(self, session: CodexExecutorSession) -> AgentResumeHandle | None:
        if not session.thread_id:
            return None
        return AgentResumeHandle(
            executor_id="codex",
            session_handle=session.thread_id,
        )

    async def _read_final_assistant_message(
        self,
        session: CodexExecutorSession,
        turn_id: str,
    ) -> str | None:
        if not session.thread_id:
            return None
        try:
            response = await session.client.thread_read(
                thread_id=session.thread_id,
                include_turns=True,
            )
        except Exception:
            return None
        return _extract_assistant_text_from_thread(response, turn_id)

    def _build_prompt(self, task: Task) -> str:
        parts = [
            f"Task: {task.title}",
            f"Goal: {task.goal}",
        ]
        if task.latest_instruction:
            parts.append(f"Latest instruction: {task.latest_instruction}")
        parts.append(
            "Work inside the current repository and return a concise final result."
        )
        return "\n".join(parts)


def _get_nested(value: object, *keys: str) -> object:
    current = value
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _extract_item_text(item: dict[str, object]) -> str | None:
    direct_text = item.get("text")
    if isinstance(direct_text, str) and direct_text.strip():
        return direct_text.strip()
    content = item.get("content")
    if not isinstance(content, list):
        return None
    parts: list[str] = []
    for entry in content:
        if isinstance(entry, dict):
            text = entry.get("text")
            if isinstance(text, str):
                parts.append(text)
    return "".join(parts).strip() or None


def _extract_question_text(params: dict[str, object]) -> str | None:
    for key in ("question", "message", "prompt"):
        value = params.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    questions = params.get("questions")
    if isinstance(questions, list):
        for question in questions:
            if isinstance(question, dict):
                prompt = question.get("question") or question.get("prompt")
                if isinstance(prompt, str) and prompt.strip():
                    return prompt.strip()
    return None


def _extract_assistant_text_from_thread(
    response: dict[str, object],
    target_turn_id: str,
) -> str | None:
    thread = response.get("thread")
    if not isinstance(thread, dict):
        return None
    turns = thread.get("turns")
    if not isinstance(turns, list):
        return None

    matched_turns = [
        turn
        for turn in turns
        if isinstance(turn, dict) and turn.get("id") == target_turn_id
    ]
    if not matched_turns:
        matched_turns = [turn for turn in turns if isinstance(turn, dict)]

    for turn in reversed(matched_turns):
        items = turn.get("items")
        if not isinstance(items, list):
            continue
        for item in reversed(items):
            if not isinstance(item, dict):
                continue
            if item.get("type") not in {"assistantMessage", "agentMessage"}:
                continue
            extracted = _extract_item_text(item)
            if extracted:
                return extracted
    return None
