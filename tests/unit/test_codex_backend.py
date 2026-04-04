from pathlib import Path

import pytest

from runtime.executors.codex.backend import CodexCliBackend
from runtime.executors.external_backend import ExternalExecutionRequest
from runtime.infrastructure.config import Settings


class FakeProcess:
    def __init__(self, *, returncode: int, stdout: bytes = b"", stderr: bytes = b"") -> None:
        self.returncode = None
        self._final_returncode = returncode
        self._stdout = stdout
        self._stderr = stderr
        self.terminated = False
        self.killed = False

    async def communicate(self):
        self.returncode = self._final_returncode
        return self._stdout, self._stderr

    async def wait(self):
        if self.returncode is None:
            self.returncode = self._final_returncode
        return self.returncode

    def terminate(self):
        self.terminated = True
        self.returncode = -15

    def kill(self):
        self.killed = True
        self.returncode = -9


def make_request() -> ExternalExecutionRequest:
    return ExternalExecutionRequest(
        run_id="run_1",
        task_id="task_1",
        session_id="session_1",
        executor_id="codex_executor",
        title="Write patch",
        goal="Update the runtime",
        latest_instruction="Update the runtime",
        input_context={"foo": "bar"},
    )


@pytest.mark.anyio
async def test_codex_backend_builds_expected_exec_command(monkeypatch, tmp_path: Path):
    seen = {}

    async def fake_create_subprocess_exec(*args, **kwargs):
        seen["args"] = args
        output_path = Path(args[args.index("--output-last-message") + 1])
        output_path.write_text("Codex completed the task.")
        return FakeProcess(returncode=0)

    monkeypatch.setattr(
        "runtime.executors.codex.backend.asyncio.create_subprocess_exec",
        fake_create_subprocess_exec,
    )

    backend = CodexCliBackend(
        Settings(
            codex_cli_path="codex",
            codex_workdir=str(tmp_path),
            codex_model="gpt-test",
            codex_timeout_seconds=30.0,
            codex_sandbox="workspace-write",
            codex_approval_policy="on-request",
        ),
        executor_id="codex_executor",
    )

    run = await backend.start(make_request())
    result = await run.wait()

    assert seen["args"][:6] == (
        "codex",
        "exec",
        "-c",
        'approval_policy="on-request"',
        "--cd",
        str(tmp_path),
    )
    assert "--sandbox" in seen["args"]
    assert "--output-last-message" in seen["args"]
    assert "--model" in seen["args"]
    assert "Update the runtime" in seen["args"][-1]
    assert result.summary == "Codex completed the task."
    assert result.artifacts[0].inline_value == "Codex completed the task."


@pytest.mark.anyio
async def test_codex_backend_returns_failure_for_non_zero_exit(monkeypatch, tmp_path: Path):
    async def fake_create_subprocess_exec(*args, **kwargs):
        return FakeProcess(returncode=1, stderr=b"auth failed")

    monkeypatch.setattr(
        "runtime.executors.codex.backend.asyncio.create_subprocess_exec",
        fake_create_subprocess_exec,
    )

    backend = CodexCliBackend(
        Settings(
            codex_cli_path="codex",
            codex_workdir=str(tmp_path),
            codex_timeout_seconds=30.0,
        ),
        executor_id="codex_executor",
    )

    run = await backend.start(make_request())
    result = await run.wait()

    assert result.failure_reason == "Codex execution failed: auth failed"


@pytest.mark.anyio
async def test_codex_backend_cancel_terminates_process(monkeypatch, tmp_path: Path):
    process = FakeProcess(returncode=0)

    async def fake_create_subprocess_exec(*args, **kwargs):
        return process

    monkeypatch.setattr(
        "runtime.executors.codex.backend.asyncio.create_subprocess_exec",
        fake_create_subprocess_exec,
    )

    backend = CodexCliBackend(
        Settings(
            codex_cli_path="codex",
            codex_workdir=str(tmp_path),
            codex_timeout_seconds=30.0,
        ),
        executor_id="codex_executor",
    )

    run = await backend.start(make_request())
    await run.cancel()

    assert process.terminated is True
