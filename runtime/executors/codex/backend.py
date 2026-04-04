from __future__ import annotations

import asyncio
import tempfile
from dataclasses import dataclass
from pathlib import Path
from shutil import rmtree

from runtime.executors.external_backend import (
    ExternalArtifact,
    ExternalExecutionRequest,
    ExternalExecutionResult,
)
from runtime.infrastructure.config import Settings
from runtime.protocols.execution import ExecutorCapability


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


@dataclass(slots=True)
class CodexCliRun:
    process: asyncio.subprocess.Process
    output_path: Path
    scratch_dir: Path
    timeout_seconds: float

    async def wait(self) -> ExternalExecutionResult:
        try:
            stdout, stderr = await asyncio.wait_for(
                self.process.communicate(), timeout=self.timeout_seconds
            )
        except TimeoutError:
            await self.cancel()
            return ExternalExecutionResult(
                failure_reason=f"Codex execution timed out after {self.timeout_seconds} seconds."
            )

        try:
            output_text = self.output_path.read_text().strip() if self.output_path.exists() else ""
        finally:
            self._cleanup()

        stdout_text = stdout.decode().strip() if stdout else ""
        stderr_text = stderr.decode().strip() if stderr else ""
        if self.process.returncode != 0:
            details = stderr_text or stdout_text or f"exit code {self.process.returncode}"
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
        self._cleanup()

    def _cleanup(self) -> None:
        if self.scratch_dir.exists():
            rmtree(self.scratch_dir, ignore_errors=True)


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
            supports_pause=False,
            supports_streaming=False,
        )

    async def start(self, request: ExternalExecutionRequest) -> CodexCliRun:
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
        )
