from synapse.executors.core import (
    ExecutorCapabilities,
    ExecutorEvent,
    ExecutorEventType,
    ExecutorResult,
    ExecutorSession,
)


def test_executor_capabilities_defaults():
    capabilities = ExecutorCapabilities(executor_type="mock")
    assert capabilities.executor_type == "mock"
    assert capabilities.supports_cancel is True
    assert capabilities.supports_resume is False


def test_executor_event_and_result_models():
    event = ExecutorEvent(
        run_id="run_1",
        session_id="sess_1",
        event_type=ExecutorEventType.PROGRESS,
        message="Working...",
    )
    result = ExecutorResult(status="completed", summary="Done.")
    session = ExecutorSession(session_id="sess_1", executor_type="mock")

    assert event.event_type == ExecutorEventType.PROGRESS
    assert result.status.value == "completed"
    assert session.executor_type == "mock"
