import pytest

from synopse.observability.logger import DiagnosticLogger
from synopse.observability.store import InMemoryDiagnosticStore


def test_logger_requires_reason_code_for_warning_error_events():
    logger = DiagnosticLogger(store=InMemoryDiagnosticStore())

    with pytest.raises(ValueError):
        logger.emit_event(
            level="WARNING",
            event_name="notify.delivery.deferred",
            component="notification.policy",
            summary="Deferred",
        )


def test_logger_sanitizes_sensitive_and_long_text_details():
    logger = DiagnosticLogger(store=InMemoryDiagnosticStore())

    logger.emit_event(
        level="INFO",
        event_name="comm.message.received",
        component="communication.brain",
        summary="Received",
        details={
            "user_text": "x" * 120,
            "api_key": "secret-key",
        },
    )

    event = list(logger.store.all())[-1]
    assert event.details["api_key"] == "[redacted]"
    assert event.details["user_text"].endswith("...")
    assert len(event.details["user_text"]) == 80


def test_diagnostic_store_filters_by_request_and_prefix():
    store = InMemoryDiagnosticStore()
    logger = DiagnosticLogger(store=store)
    logger.emit_event(
        level="INFO",
        event_name="api.message.accepted",
        component="api.messages",
        summary="Accepted",
        request_id="req-1",
    )
    logger.emit_event(
        level="INFO",
        event_name="exec.run.started",
        component="execution.run_manager",
        summary="Started",
        request_id="req-2",
        run_id="run-1",
    )

    events = store.query(request_id="req-1", event_prefix="api.")

    assert len(events) == 1
    assert events[0].event_name == "api.message.accepted"
