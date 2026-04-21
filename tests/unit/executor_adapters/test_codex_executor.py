from __future__ import annotations

import os
import stat
import sys
import textwrap

import pytest

from synapse.executor_adapters.codex import CodexExecutor
from synapse.protocol import ExecutionRun, Task


def _write_fake_codex(tmp_path, *, auth_ok: bool = True):
    script = tmp_path / "fake-codex"
    script.write_text(
        textwrap.dedent(
            f"""\
            #!{sys.executable}
            import json
            import sys

            thread_counter = 0
            turn_counter = 0
            auth_ok = {str(auth_ok)}
            turns_by_thread = {{}}

            def send(payload):
                sys.stdout.write(json.dumps(payload) + "\\n")
                sys.stdout.flush()

            for raw in sys.stdin:
                if not raw.strip():
                    continue
                msg = json.loads(raw)
                method = msg.get("method")
                params = msg.get("params", {{}})
                request_id = msg.get("id")
                if method == "initialize":
                    send({{"id": request_id, "result": {{"ok": True}}}})
                elif method == "initialized":
                    continue
                elif method == "account/read":
                    send(
                        {{
                            "id": request_id,
                            "result": {{
                                "account": {{"type": "apiKey"}} if auth_ok else None,
                                "requiresOpenaiAuth": True,
                            }},
                        }}
                    )
                elif method == "thread/start":
                    thread_counter += 1
                    thread_id = f"thread-{{thread_counter}}"
                    turns_by_thread.setdefault(thread_id, [])
                    send({{"id": request_id, "result": {{"thread": {{"id": thread_id}}}}}})
                elif method == "thread/fork":
                    original = params.get("threadId")
                    if original == "bad-thread":
                        send({{"id": request_id, "error": {{"message": "bad thread"}}}})
                    else:
                        forked = f"fork-{{original}}"
                        turns_by_thread.setdefault(forked, [])
                        send(
                            {{
                                "id": request_id,
                                "result": {{"thread": {{"id": forked}}}},
                            }}
                        )
                elif method == "thread/read":
                    thread_id = params.get("threadId")
                    send(
                        {{
                            "id": request_id,
                            "result": {{
                                "thread": {{
                                    "id": thread_id,
                                    "turns": turns_by_thread.get(thread_id, []),
                                }}
                            }},
                        }}
                    )
                elif method == "turn/start":
                    turn_counter += 1
                    turn_id = f"turn-{{turn_counter}}"
                    thread_id = params["threadId"]
                    prompt = params["input"][0]["text"]
                    send(
                        {{
                            "id": request_id,
                            "result": {{"turn": {{"id": turn_id, "status": "inProgress"}}}},
                        }}
                    )
                    if "Need confirmation" in prompt:
                        turns_by_thread.setdefault(thread_id, []).append(
                            {{
                                "id": turn_id,
                                "items": [],
                            }}
                        )
                        send(
                            {{
                                "method": "question/request_user_input",
                                "params": {{
                                    "turnId": turn_id,
                                    "question": "Need confirmation?",
                                }},
                            }}
                        )
                    elif "Need permission" in prompt:
                        turns_by_thread.setdefault(thread_id, []).append(
                            {{
                                "id": turn_id,
                                "items": [],
                            }}
                        )
                        send(
                            {{
                                "id": f"approval-{{turn_id}}",
                                "method": "item/permissions/requestApproval",
                                "params": {{
                                    "threadId": thread_id,
                                    "turnId": turn_id,
                                    "reason": "Need permission to delete that folder.",
                                    "permissions": {{
                                        "fileSystem": {{"writeRoots": ["/tmp"]}}
                                    }},
                                }},
                            }}
                        )
                    elif "fail task" in prompt:
                        turns_by_thread.setdefault(thread_id, []).append(
                            {{
                                "id": turn_id,
                                "items": [],
                            }}
                        )
                        send(
                            {{
                                "method": "turn/completed",
                                "params": {{
                                    "turn": {{
                                        "id": turn_id,
                                        "status": "failed",
                                        "error": {{"message": "fake failure"}},
                                    }}
                                }},
                            }}
                        )
                    elif "Readback only" in prompt:
                        turns_by_thread.setdefault(thread_id, []).append(
                            {{
                                "id": turn_id,
                                "items": [
                                    {{
                                        "type": "agentMessage",
                                        "text": "Final text from thread read.",
                                    }}
                                ],
                            }}
                        )
                        send(
                            {{
                                "method": "turn/completed",
                                "params": {{
                                    "turn": {{
                                        "id": turn_id,
                                        "status": "completed",
                                        "error": None,
                                    }}
                                }},
                            }}
                        )
                    else:
                        turns_by_thread.setdefault(thread_id, []).append(
                            {{
                                "id": turn_id,
                                "items": [
                                    {{
                                        "type": "agentMessage",
                                        "text": "Done from Codex.",
                                    }}
                                ],
                            }}
                        )
                        send(
                            {{
                                "method": "item/completed",
                                "params": {{
                                    "turnId": turn_id,
                                    "item": {{
                                        "type": "agentMessage",
                                        "text": "Done from Codex.",
                                    }},
                                }},
                            }}
                        )
                        send(
                            {{
                                "method": "turn/completed",
                                "params": {{
                                    "turn": {{
                                        "id": turn_id,
                                        "status": "completed",
                                        "error": None,
                                    }}
                                }},
                            }}
                        )
                else:
                    send({{"id": request_id, "error": {{"message": f"unknown method: {{method}}"}}}})
            """
        )
    )
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    return script


def _write_noisy_fake_codex(tmp_path):
    script = tmp_path / "fake-codex-noisy"
    script.write_text(
        textwrap.dedent(
            f"""\
            #!{sys.executable}
            import json
            import sys

            def send(payload):
                sys.stdout.write(json.dumps(payload) + "\\n")
                sys.stdout.flush()

            for raw in sys.stdin:
                if not raw.strip():
                    continue
                msg = json.loads(raw)
                method = msg.get("method")
                request_id = msg.get("id")
                if method == "initialize":
                    send({{"id": request_id, "result": {{"ok": True}}}})
                elif method == "initialized":
                    continue
                elif method == "account/read":
                    send({{"id": request_id, "result": {{"account": {{"type": "apiKey"}}, "requiresOpenaiAuth": True}}}})
                elif method == "thread/start":
                    send({{"id": request_id, "result": {{"thread": {{"id": "thread-1"}}}}}})
                elif method == "turn/start":
                    send({{"id": request_id, "result": {{"turn": {{"id": "turn-1", "status": "inProgress"}}}}}})
                    send({{"method": "item/started", "params": {{"turnId": "turn-1", "item": {{"type": "reasoning"}}}}}})
                    send({{"method": "item/completed", "params": {{"turnId": "turn-1", "item": {{"type": "webSearch"}}}}}})
                    send({{"method": "item/started", "params": {{"turnId": "turn-1", "item": {{"type": "agentMessage"}}}}}})
                    send({{"method": "item/completed", "params": {{"turnId": "turn-1", "item": {{"type": "agentMessage", "text": "Useful answer from Codex."}}}}}})
                    send({{"method": "turn/completed", "params": {{"turn": {{"id": "turn-1", "status": "completed", "error": None}}}}}})
                elif method == "thread/read":
                    send({{"id": request_id, "result": {{"thread": {{"id": "thread-1", "turns": [{{"id": "turn-1", "items": [{{"type": "agentMessage", "text": "Useful answer from Codex."}}]}}]}}}}}})
                else:
                    send({{"id": request_id, "error": {{"message": "unknown"}}}})
            """
        )
    )
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    return script


@pytest.mark.anyio
async def test_codex_executor_completes_task_with_fake_app_server(tmp_path):
    command = _write_fake_codex(tmp_path)
    executor = CodexExecutor(command=str(command))
    session = await executor.create_session(str(tmp_path))
    task = Task(
        task_id="task-1",
        root_task_id="task-1",
        title="Codex task",
        goal="Say hello",
    )
    run = ExecutionRun(
        run_id="run-1",
        task_id="task-1",
        execution_session_id="exec-1",
        executor_type="codex",
    )

    events = [event async for event in executor.run_task(run, task, session)]

    assert events[-1].event_type.value == "completed"
    assert events[-1].message == "Done from Codex."
    assert session.thread_id == "thread-1"
    await session.close()


@pytest.mark.anyio
async def test_codex_executor_forks_existing_thread_on_follow_up(tmp_path):
    command = _write_fake_codex(tmp_path)
    executor = CodexExecutor(command=str(command))
    session = await executor.create_session(str(tmp_path))
    session.thread_id = "thread-1"
    task = Task(
        task_id="task-1",
        root_task_id="task-1",
        title="Follow-up task",
        goal="Say hello again",
    )
    run = ExecutionRun(
        run_id="run-2",
        task_id="task-1",
        execution_session_id="exec-1",
        executor_type="codex",
    )

    events = [event async for event in executor.run_task(run, task, session)]

    assert events[-1].event_type.value == "completed"
    assert session.thread_id == "fork-thread-1"
    await session.close()


@pytest.mark.anyio
async def test_codex_executor_blocks_when_user_input_is_requested(tmp_path):
    command = _write_fake_codex(tmp_path)
    executor = CodexExecutor(command=str(command))
    session = await executor.create_session(str(tmp_path))
    task = Task(
        task_id="task-2",
        root_task_id="task-2",
        title="Blocked task",
        goal="Need confirmation",
    )
    run = ExecutionRun(
        run_id="run-3",
        task_id="task-2",
        execution_session_id="exec-2",
        executor_type="codex",
    )

    event_stream = executor.run_task(run, task, session)
    event = await anext(event_stream)

    assert event.event_type.value == "blocked"
    assert event.message == "Need confirmation?"
    await event_stream.aclose()
    await session.close()


@pytest.mark.anyio
async def test_codex_executor_blocks_when_permission_approval_is_requested(tmp_path):
    command = _write_fake_codex(tmp_path)
    executor = CodexExecutor(command=str(command))
    session = await executor.create_session(str(tmp_path))
    task = Task(
        task_id="task-2b",
        root_task_id="task-2b",
        title="Permission task",
        goal="Need permission",
    )
    run = ExecutionRun(
        run_id="run-2b",
        task_id="task-2b",
        execution_session_id="exec-2b",
        executor_type="codex",
    )

    event_stream = executor.run_task(run, task, session)
    event = await anext(event_stream)

    assert event.event_type.value == "blocked"
    assert event.message == "Need permission to delete that folder."
    assert event.metadata["interaction_kind"] == "permission"
    await event_stream.aclose()
    await session.close()


@pytest.mark.anyio
async def test_codex_executor_reads_final_text_from_thread_when_no_live_assistant_item(tmp_path):
    command = _write_fake_codex(tmp_path)
    executor = CodexExecutor(command=str(command))
    session = await executor.create_session(str(tmp_path))
    task = Task(
        task_id="task-3",
        root_task_id="task-3",
        title="Readback task",
        goal="Readback only",
    )
    run = ExecutionRun(
        run_id="run-4",
        task_id="task-3",
        execution_session_id="exec-3",
        executor_type="codex",
    )

    events = [event async for event in executor.run_task(run, task, session)]

    assert events[-1].event_type.value == "completed"
    assert events[-1].message == "Final text from thread read."
    await session.close()


@pytest.mark.anyio
async def test_codex_executor_drops_low_value_item_lifecycle_progress(tmp_path):
    command = _write_noisy_fake_codex(tmp_path)
    executor = CodexExecutor(command=str(command))
    session = await executor.create_session(str(tmp_path))
    task = Task(
        task_id="task-4",
        root_task_id="task-4",
        title="Noisy task",
        goal="Filter noisy progress",
    )
    run = ExecutionRun(
        run_id="run-5",
        task_id="task-4",
        execution_session_id="exec-4",
        executor_type="codex",
    )

    events = [event async for event in executor.run_task(run, task, session)]

    assert [event.event_type.value for event in events] == ["progress", "completed"]
    assert events[0].message == "Useful answer from Codex."
    assert events[1].message == "Useful answer from Codex."
    await session.close()
