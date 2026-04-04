import json
from pathlib import Path

import pytest

from runtime.executors.codex.backend import CodexCliBackend
from runtime.executors.external_backend import ExternalExecutionRequest
from runtime.infrastructure.config import Settings


class FakeStream:
    def __init__(self, lines: list[bytes] | None = None, read_bytes: bytes = b"") -> None:
        self._lines = list(lines or [])
        self._read_bytes = read_bytes

    async def readline(self) -> bytes:
        if self._lines:
            return self._lines.pop(0)
        return b""

    async def read(self) -> bytes:
        return self._read_bytes


class FakeProcess:
    def __init__(
        self,
        *,
        returncode: int,
        stdout_lines: list[bytes] | None = None,
        stderr: bytes = b"",
    ) -> None:
        self.returncode = None
        self._final_returncode = returncode
        self.stdout = FakeStream(lines=stdout_lines)
        self.stderr = FakeStream(read_bytes=stderr)
        self.terminated = False
        self.killed = False

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
async def test_codex_backend_builds_expected_exec_command_and_emits_updates(
    monkeypatch, tmp_path: Path
):
    seen = {}

    async def fake_create_subprocess_exec(*args, **kwargs):
        seen["args"] = args
        output_path = Path(args[args.index("--output-last-message") + 1])
        output_path.write_text("Codex completed the task.")
        return FakeProcess(
            returncode=0,
            stdout_lines=[
                b'{"type":"thread.started","thread_id":"thread_1"}\n',
                b'{"type":"turn.started"}\n',
                json.dumps(
                    {
                        "type": "exec_command.started",
                        "command": "pytest",
                    }
                ).encode()
                + b"\n",
            ],
        )

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

    updates = []

    async def callback(update):
        updates.append(update)

    run = await backend.start(make_request(), update_callback=callback)
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
    assert "--json" in seen["args"]
    assert "--color" in seen["args"]
    assert "--output-last-message" in seen["args"]
    assert "--model" in seen["args"]
    assert "Update the runtime" in seen["args"][-1]
    assert [update.event.event_type.value for update in updates] == ["started", "progress"]
    assert updates[1].persist is False
    assert updates[1].event.progress_message == "Running command: pytest"
    assert result.summary == "Codex completed the task."
    assert result.artifacts[0].inline_value == "Codex completed the task."


@pytest.mark.anyio
async def test_codex_backend_returns_failure_for_non_zero_exit(monkeypatch, tmp_path: Path):
    async def fake_create_subprocess_exec(*args, **kwargs):
        return FakeProcess(
            returncode=1,
            stdout_lines=[
                b'{"type":"turn.failed","error":{"message":"auth failed"}}\n',
            ],
        )

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
async def test_codex_backend_returns_blocked_result_for_input_request(
    monkeypatch, tmp_path: Path
):
    async def fake_create_subprocess_exec(*args, **kwargs):
        return FakeProcess(
            returncode=0,
            stdout_lines=[
                b'{"type":"turn.started"}\n',
                b'{"type":"turn.waiting_for_input","message":"Need clarification from you on the target file."}\n',
            ],
        )

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

    assert result.blocked_reason == "Need clarification from you on the target file."


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
