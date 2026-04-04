from __future__ import annotations

import asyncio
import json
import re
import tempfile
from pathlib import Path
from shutil import rmtree
from typing import Any

from runtime.executors.base import (
    ExecutionCallback,
    durable_execution_update,
    transient_execution_update,
)
from runtime.executors.external_backend import (
    ExternalArtifact,
    ExternalExecutionRequest,
    ExternalExecutionResult,
)
from runtime.infrastructure.config import Settings
from runtime.infrastructure.ids import new_id
from runtime.protocols.execution import ExecutionEvent, ExecutionEventType, ExecutorCapability
from runtime.protocols.tasks import TaskStatus


def _build_codex_prompt(request: ExternalExecutionRequest) -> str:
    latest_instruction = request.latest_instruction or request.goal
    return "\n".join(
        [
            "You are executing a Synopse task.",
            f"session_id: {request.session_id}",
            f"task_id: {request.task_id}",
            f"title: {request.title}",
            f"goal: {request.goal}",
            f"latest_instruction: {latest_instruction}",
            f"input_context: {request.input_context}",
            "Work only within the provided repository and return a concise final result.",
        ]
    )


def _normalize_codex_event_type(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")


def _extract_nested_text(value: Any) -> str | None:
    if isinstance(value, str):
        cleaned = value.strip()
        return cleaned or None
    if isinstance(value, dict):
        for key in ("message", "text", "summary", "reason", "title", "delta"):
            extracted = _extract_nested_text(value.get(key))
            if extracted:
                return extracted
    return None


def _extract_codex_message(payload: dict[str, Any]) -> str | None:
    for key in ("message", "error", "detail", "details"):
        extracted = _extract_nested_text(payload.get(key))
        if extracted:
            return extracted
    return None


def _humanize_codex_event_type(value: str) -> str:
    words = _normalize_codex_event_type(value).split("_")
    if not words:
        return "Task is making progress."
    return f"Codex {' '.join(words)}."


def _extract_progress_message(payload: dict[str, Any]) -> str | None:
    message = _extract_codex_message(payload)
    if message:
        return message
    tool_name = payload.get("tool_name") or payload.get("tool")
    if isinstance(tool_name, str) and tool_name.strip():
        return f"Using tool: {tool_name.strip()}."
    command = payload.get("command")
    if isinstance(command, str) and command.strip():
        return f"Running command: {command.strip()}"
    path = payload.get("path") or payload.get("file_path")
    if isinstance(path, str) and path.strip():
        return f"Updating {path.strip()}."
    raw_type = payload.get("type")
    if isinstance(raw_type, str) and raw_type.strip():
        return _humanize_codex_event_type(raw_type)
    return None


def _is_blocked_codex_event(normalized_type: str, payload: dict[str, Any]) -> bool:
    if any(
        token in normalized_type
        for token in ("waiting_for_input", "need_input", "needs_input", "blocked")
    ):
        return True
    message = (_extract_codex_message(payload) or "").lower()
    return any(
        phrase in message
        for phrase in (
            "waiting for your input",
            "need more information from you",
            "need clarification from you",
            "user input required",
        )
    )


def _should_emit_progress(normalized_type: str, payload: dict[str, Any]) -> bool:
    if normalized_type in {
        "thread_started",
        "thread_completed",
        "turn_started",
        "turn_completed",
    }:
        return False
    if "output_text" in normalized_type:
        return False
    if normalized_type.endswith("failed") or normalized_type == "error":
        return False
    interesting_tokens = (
        "tool",
        "exec_command",
        "apply_patch",
        "patch",
        "agent_message",
        "agent_reasoning",
        "plan",
        "search",
        "mcp",
    )
    if any(token in normalized_type for token in interesting_tokens):
        return True
    return _extract_codex_message(payload) is not None and normalized_type not in {"turn"}


class CodexCliRun:
    def __init__(
        self,
        *,
        process: asyncio.subprocess.Process,
        output_path: Path,
        scratch_dir: Path,
        timeout_seconds: float,
        executor_id: str,
        task_id: str,
        update_callback: ExecutionCallback | None = None,
    ) -> None:
        self.process = process
        self.output_path = output_path
        self.scratch_dir = scratch_dir
        self.timeout_seconds = timeout_seconds
        self._executor_id = executor_id
        self._task_id = task_id
        self._update_callback = update_callback
        self._started_emitted = False
        self._blocked_reason: str | None = None
        self._failure_message: str | None = None
        self._last_progress_message: str | None = None
        self._stdout_task = asyncio.create_task(self._consume_stdout())
        self._stderr_task = asyncio.create_task(self._read_stream(self.process.stderr))

    async def wait(self) -> ExternalExecutionResult:
        try:
            await asyncio.wait_for(self.process.wait(), timeout=self.timeout_seconds)
        except TimeoutError:
            await self.cancel()
            return ExternalExecutionResult(
                failure_reason=f"Codex execution timed out after {self.timeout_seconds} seconds."
            )

        try:
            stdout_text = await self._stdout_task
            stderr_text = await self._stderr_task
            output_text = self.output_path.read_text().strip() if self.output_path.exists() else ""
        finally:
            self._cleanup()

        await self._emit_started_once()
        if self._blocked_reason and self.process.returncode == 0:
            return ExternalExecutionResult(
                blocked_reason=self._blocked_reason,
                metadata={"source": "codex_json"},
            )

        if self.process.returncode != 0:
            details = (
                self._failure_message
                or stderr_text
                or stdout_text
                or f"exit code {self.process.returncode}"
            )
            return ExternalExecutionResult(
                failure_reason=f"Codex execution failed: {details}"
            )

        summary = output_text or stdout_text or "Codex task completed."
        artifacts = (
            [
                ExternalArtifact(
                    artifact_type="text",
                    name="codex_response",
                    mime_type="text/plain",
                    inline_value=summary,
                )
            ]
            if summary
            else []
        )
        return ExternalExecutionResult(
            summary=summary,
            artifacts=artifacts,
        )

    async def cancel(self) -> None:
        if self.process.returncode is None:
            self.process.terminate()
            try:
                await asyncio.wait_for(self.process.wait(), timeout=3)
            except TimeoutError:
                self.process.kill()
                await self.process.wait()
        await asyncio.gather(
            self._stdout_task,
            self._stderr_task,
            return_exceptions=True,
        )
        self._cleanup()

    def _cleanup(self) -> None:
        if self.scratch_dir.exists():
            rmtree(self.scratch_dir, ignore_errors=True)

    async def _emit_started_once(self) -> None:
        if self._started_emitted:
            return
        self._started_emitted = True
        if self._update_callback is None:
            return
        await self._update_callback(
            durable_execution_update(
                ExecutionEvent(
                    event_id=new_id("exec"),
                    task_id=self._task_id,
                    executor_id=self._executor_id,
                    event_type=ExecutionEventType.STARTED,
                    status=TaskStatus.RUNNING,
                    progress_message="Task started.",
                    metadata={"source": "codex_json"},
                )
            )
        )

    async def _emit_progress(self, message: str, *, event_type: str) -> None:
        cleaned = message.strip()
        if not cleaned or cleaned == self._last_progress_message:
            return
        await self._emit_started_once()
        self._last_progress_message = cleaned
        if self._update_callback is None:
            return
        await self._update_callback(
            transient_execution_update(
                ExecutionEvent(
                    event_id=new_id("exec"),
                    task_id=self._task_id,
                    executor_id=self._executor_id,
                    event_type=ExecutionEventType.PROGRESS,
                    status=TaskStatus.RUNNING,
                    progress_message=cleaned,
                    metadata={
                        "source": "codex_json",
                        "codex_event_type": event_type,
                    },
                )
            )
        )

    async def _consume_stdout(self) -> str:
        if self.process.stdout is None:
            return ""
        non_json_lines: list[str] = []
        while True:
            line = await self.process.stdout.readline()
            if not line:
                break
            decoded = line.decode(errors="replace").strip()
            if not decoded:
                continue
            try:
                payload = json.loads(decoded)
            except json.JSONDecodeError:
                non_json_lines.append(decoded)
                continue
            if isinstance(payload, dict):
                await self._handle_json_event(payload)
        return "\n".join(non_json_lines).strip()

    async def _read_stream(self, stream) -> str:
        if stream is None:
            return ""
        content = await stream.read()
        return content.decode(errors="replace").strip()

    async def _handle_json_event(self, payload: dict[str, Any]) -> None:
        raw_type = payload.get("type")
        if not isinstance(raw_type, str) or not raw_type.strip():
            return

        normalized_type = _normalize_codex_event_type(raw_type)
        if normalized_type == "turn_started":
            await self._emit_started_once()
            return
        if normalized_type.endswith("failed"):
            self._failure_message = _extract_codex_message(payload) or raw_type
            return
        if _is_blocked_codex_event(normalized_type, payload):
            self._blocked_reason = (
                _extract_codex_message(payload)
                or "Task needs clarification before it can continue."
            )
            return
        if not _should_emit_progress(normalized_type, payload):
            return

        message = _extract_progress_message(payload)
        if message:
            await self._emit_progress(message, event_type=raw_type)


class CodexCliBackend:
    def __init__(self, settings: Settings, executor_id: str) -> None:
        self._settings = settings
        self._executor_id = executor_id

    def get_capabilities(self) -> ExecutorCapability:
        return ExecutorCapability(
            executor_id=self._executor_id,
            label="Codex Executor",
            capability_tags=["generic", "coding", "external", "agent"],
            supports_cancel=True,
            supports_streaming=True,
        )

    async def start(
        self,
        request: ExternalExecutionRequest,
        update_callback: ExecutionCallback | None = None,
    ) -> CodexCliRun:
        scratch_dir = Path(tempfile.mkdtemp(prefix="synopse-codex-"))
        output_path = scratch_dir / "last-message.txt"
        command = [
            self._settings.codex_cli_path,
            "exec",
            "-c",
            f'approval_policy="{self._settings.codex_approval_policy}"',
            "--cd",
            self._settings.codex_workdir,
            "--sandbox",
            self._settings.codex_sandbox,
            "--ephemeral",
            "--color",
            "never",
            "--json",
            "--output-last-message",
            str(output_path),
        ]
        if self._settings.codex_model:
            command.extend(["--model", self._settings.codex_model])
        command.append(_build_codex_prompt(request))
        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        return CodexCliRun(
            process=process,
            output_path=output_path,
            scratch_dir=scratch_dir,
            timeout_seconds=self._settings.codex_timeout_seconds,
            executor_id=self._executor_id,
            task_id=request.task_id,
            update_callback=update_callback,
        )
