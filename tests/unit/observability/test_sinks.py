from __future__ import annotations

from io import StringIO

from newbro.observability.bootstrap import build_stdout_sink
from newbro.observability.schema import DiagnosticEvent
from newbro.observability.sinks.pretty import PrettyDiagnosticSink, render_pretty_event
from newbro.observability.sinks.stdout import StdoutDiagnosticSink
from newbro.runtime.config import Settings


class TtyStringIO(StringIO):
    def isatty(self) -> bool:
        return True


class PipeStringIO(StringIO):
    def isatty(self) -> bool:
        return False


def test_build_stdout_sink_uses_pretty_for_tty_by_default():
    sink = build_stdout_sink(Settings(), stream=TtyStringIO())

    assert isinstance(sink, PrettyDiagnosticSink)


def test_build_stdout_sink_uses_json_for_piped_output_by_default():
    sink = build_stdout_sink(Settings(), stream=PipeStringIO())

    assert isinstance(sink, StdoutDiagnosticSink)


def test_build_stdout_sink_respects_explicit_json_override():
    sink = build_stdout_sink(Settings(log_format="json"), stream=TtyStringIO())

    assert isinstance(sink, StdoutDiagnosticSink)


def test_build_stdout_sink_respects_explicit_pretty_override():
    sink = build_stdout_sink(Settings(log_format="pretty"), stream=PipeStringIO())

    assert isinstance(sink, PrettyDiagnosticSink)


def test_pretty_sink_renders_colored_compact_line():
    event = DiagnosticEvent(
        level="ERROR",
        event_name="exec.run.failed",
        component="execution.run_manager",
        summary="Execution run state updated",
        conversation_id="session-1",
        request_id="req-1",
        task_id="task-1",
        run_id="run-1",
        reason_code="executor_run_failed",
        details={
            "message": "x" * 80,
            "attempt": 1,
            "executor": "mock",
            "extra": "value",
            "overflow": "ignored",
        },
    )

    rendered = render_pretty_event(event, color_enabled=True)

    assert "\033[31m" in rendered
    assert "exec.run.failed" in rendered
    assert "conversation=session-1" in rendered
    assert "request=req-1" in rendered
    assert "task=task-1" in rendered
    assert "run=run-1" in rendered
    assert "reason=executor_run_failed" in rendered
    assert "details[" in rendered
    assert "..." in rendered
    assert "\n" not in rendered


def test_pretty_sink_renders_multiline_block_for_comm_llm_request_built():
    event = DiagnosticEvent(
        level="INFO",
        event_name="comm.llm.request_built",
        component="communication.llm",
        summary="LLM interaction recorded",
        conversation_id="session-1",
        request_id="req-1",
        details={
            "prompt_sections": ["identity", "runtime_context"],
            "available_tools": ["create_task", "query_task_detail"],
            "system_messages": [
                {
                    "role": "system",
                    "content": "You are the Communication Brain for Newbro.",
                },
                {
                    "role": "system",
                    "content": '{"conversation_id":"conv-1","task_execution_details":{"task-1":[{"text":"meaningful progress"}]}}',
                },
            ],
        },
    )

    rendered = render_pretty_event(event, color_enabled=False)

    assert "comm.llm.request_built" in rendered
    assert "conversation=session-1" in rendered
    assert "\n" in rendered
    assert "prompt_sections: identity, runtime_context" in rendered
    assert "available_tools: create_task, query_task_detail" in rendered
    assert "system[0:identity]:" in rendered
    assert "You are the Communication Brain for Newbro." in rendered
    assert "system[1:runtime_context]:" in rendered
    assert '"conversation_id": "conv-1"' in rendered
    assert '"task_execution_details"' in rendered
    assert "meaningful progress" in rendered


def test_pretty_sink_renders_raw_runtime_context_when_not_valid_json():
    event = DiagnosticEvent(
        level="INFO",
        event_name="comm.llm.request_built",
        component="communication.llm",
        summary="LLM interaction recorded",
        details={
            "prompt_sections": ["runtime_context"],
            "system_messages": [
                {
                    "role": "system",
                    "content": "{not valid json but should still be shown fully}",
                }
            ],
        },
    )

    rendered = render_pretty_event(event, color_enabled=False)

    assert "system[0:runtime_context]:" in rendered
    assert "{not valid json but should still be shown fully}" in rendered


def test_pretty_sink_can_disable_color():
    event = DiagnosticEvent(
        level="WARNING",
        event_name="notify.delivery.deferred",
        component="notification.policy",
        summary="Notification delivery deferred",
        reason_code="notification_deferred_assistant_busy",
    )

    rendered = render_pretty_event(event, color_enabled=False)

    assert "\033[" not in rendered
    assert "WARNING " in rendered


def test_stdout_sink_emits_json_line():
    stream = StringIO()
    sink = StdoutDiagnosticSink(stream=stream)
    event = DiagnosticEvent(
        level="INFO",
        event_name="api.message.accepted",
        component="api.messages",
        summary="Accepted",
    )

    sink.emit(event)

    output = stream.getvalue()
    assert output.endswith("\n")
    assert "\"event_name\":\"api.message.accepted\"" in output
