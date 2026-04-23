from __future__ import annotations

import logging

from synapse.api.logging import DiagnosticsTimelineAccessFilter, install_access_log_filters
from synapse.runtime.config import Settings


def _access_record(method: str, path: str) -> logging.LogRecord:
    return logging.LogRecord(
        name="uvicorn.access",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg='%s - "%s %s HTTP/%s" %d',
        args=("127.0.0.1:1234", method, path, "1.1", 200),
        exc_info=None,
    )


def test_diagnostics_timeline_access_filter_suppresses_polling_requests():
    record = _access_record(
        "GET",
        "/api/sessions/session-1/diagnostics/timeline?after_sequence=75&min_level=DEBUG",
    )

    assert DiagnosticsTimelineAccessFilter().filter(record) is False


def test_diagnostics_timeline_access_filter_keeps_other_requests():
    assert DiagnosticsTimelineAccessFilter().filter(_access_record("GET", "/api/sessions/session-1")) is True
    assert DiagnosticsTimelineAccessFilter().filter(
        _access_record("POST", "/api/sessions/session-1/messages")
    ) is True


def test_install_access_log_filters_is_idempotent(monkeypatch):
    logger = logging.getLogger("uvicorn.access.test")
    original_filters = list(logger.filters)
    logger.filters.clear()

    original_get_logger = logging.getLogger
    monkeypatch.setattr(
        logging,
        "getLogger",
        lambda name=None: logger if name == "uvicorn.access" else original_get_logger(name),
    )

    install_access_log_filters(Settings())
    install_access_log_filters(Settings())

    filters = [item for item in logger.filters if isinstance(item, DiagnosticsTimelineAccessFilter)]
    assert len(filters) == 1

    logger.filters[:] = original_filters


def test_install_access_log_filters_respects_disable_flag(monkeypatch):
    logger = logging.getLogger("uvicorn.access.test.disabled")
    original_filters = list(logger.filters)
    logger.filters.clear()

    original_get_logger = logging.getLogger
    monkeypatch.setattr(
        logging,
        "getLogger",
        lambda name=None: logger if name == "uvicorn.access" else original_get_logger(name),
    )

    install_access_log_filters(Settings(quiet_diagnostics_access_logs=False))

    assert not any(isinstance(item, DiagnosticsTimelineAccessFilter) for item in logger.filters)

    logger.filters[:] = original_filters
