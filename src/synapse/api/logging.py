from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from synapse.runtime.config import Settings


class DiagnosticsTimelineAccessFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        method, path = _extract_request_parts(record)
        if method == "GET" and "/diagnostics/timeline" in path:
            return False
        return True


def install_access_log_filters(settings: "Settings") -> None:
    if not settings.quiet_diagnostics_access_logs:
        return

    logger = logging.getLogger("uvicorn.access")
    if any(isinstance(item, DiagnosticsTimelineAccessFilter) for item in logger.filters):
        return
    logger.addFilter(DiagnosticsTimelineAccessFilter())


def _extract_request_parts(record: logging.LogRecord) -> tuple[str, str]:
    args = record.args
    if isinstance(args, tuple) and len(args) >= 3:
        method = str(args[1])
        path = str(args[2])
        return method, path
    message = record.getMessage()
    if '"' not in message:
        return "", ""
    try:
        request_part = message.split('"', 2)[1]
        method, path, *_ = request_part.split(" ")
    except (IndexError, ValueError):
        return "", ""
    return method, path
