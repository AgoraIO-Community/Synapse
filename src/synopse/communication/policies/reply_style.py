from __future__ import annotations

from typing import Any

from synopse.protocol import TaskSummary


def render_reply(
    conversational_act: str,
    *,
    tool_results: dict[str, Any],
    reply_override: str | None = None,
) -> str:
    if reply_override:
        return reply_override

    if conversational_act == "acknowledge_and_start":
        return "Okay, I'll take care of that."
    if conversational_act == "acknowledge_and_modify":
        return "Okay, I'll adjust that."
    if conversational_act == "acknowledge_and_hold":
        return "Okay, I'll hold that for now."
    if conversational_act in {"inform_progress", "report_completion"}:
        summary = _extract_summary(tool_results)
        if summary is not None:
            return summary
        return "Here's the latest progress."
    if conversational_act == "request_clarification":
        return "Can you clarify which task you mean?"
    return "Okay."


def _extract_summary(tool_results: dict[str, Any]) -> str | None:
    for result in tool_results.values():
        if isinstance(result, TaskSummary):
            return result.conversational_summary or result.operational_summary
        if isinstance(result, dict):
            summary = result.get("summary")
            if isinstance(summary, TaskSummary):
                return summary.conversational_summary or summary.operational_summary
    return None
