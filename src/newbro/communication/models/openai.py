from __future__ import annotations

import json
from inspect import isawaitable
from typing import Any
from uuid import uuid4

from newbro.infrastructure.llm import OpenAIProvider
from newbro.protocol import NotificationCandidate, Task, TaskCommand, TaskSummary

from ..context import CommunicationContext
from ..model import (
    CommunicationModelResult,
    LlmToolInvocationTrace,
    LlmTraceCallback,
    LlmTraceRecord,
    TextDeltaCallback,
    ToolCallCallback,
    ToolCallError,
    ToolCallRecord,
)
from ..policies import infer_conversational_act
from ..prompts.builders import build_notification_prompt_request, build_reply_prompt_request
from ..prompts.runtime_context import build_notification_candidates_payload
from ..tools import ToolRegistry
from ..types import ToolInvocationRecord


class OpenAICommunicationModel:
    def __init__(self, provider: OpenAIProvider) -> None:
        self._provider = provider

    async def respond(
        self,
        *,
        user_text: str,
        context: CommunicationContext,
        tool_registry: ToolRegistry,
        on_text_delta: TextDeltaCallback | None = None,
        on_trace: LlmTraceCallback | None = None,
        on_tool_call: ToolCallCallback | None = None,
    ) -> CommunicationModelResult:
        prompt_request = build_reply_prompt_request(user_text=user_text, context=context)
        trace_id = f"llm-msg-{uuid4().hex[:8]}"
        if on_trace is not None:
            await _emit_trace(
                on_trace,
                LlmTraceRecord(
                    trace_id=trace_id,
                    source="message",
                    phase="request_built",
                    prompt_sections=prompt_request.prompt_sections,
                    messages=prompt_request.messages,
                    user_text=user_text,
                    available_tools=context.available_tools,
                ),
            )
        reply_text, invocations = await self._provider.run_tool_calling(
            messages=prompt_request.messages,
            tools=tool_registry.openai_tools,
            tool_runner=lambda name, args: tool_registry.get(name).invoke(**args),
            on_text_delta=on_text_delta,
            on_tool_call=(
                None if on_tool_call is None else lambda payload: _emit_tool_call_record(on_tool_call, payload)
            ),
        )
        tool_invocations = [
            ToolInvocationRecord(tool_name=item["name"], args=item["args"], result=item["result"])
            for item in invocations
        ]
        result = CommunicationModelResult(
            reply_text=reply_text,
            tool_invocations=tool_invocations,
            affected_task_ids=[
                task_id
                for task_id in (_extract_task_id(item["result"]) for item in invocations)
                if task_id
            ],
            conversational_act=infer_conversational_act(tool_invocations, reply_text),
        )
        if on_trace is not None:
            await _emit_trace(
                on_trace,
                LlmTraceRecord(
                    trace_id=trace_id,
                    source="message",
                    phase="response_completed",
                    prompt_sections=prompt_request.prompt_sections,
                    messages=prompt_request.messages,
                    user_text=user_text,
                    reply_text=result.reply_text,
                    available_tools=context.available_tools,
                    tool_invocations=[
                        LlmToolInvocationTrace(
                            tool_name=item["name"],
                            args=item["args"],
                            result_summary=_summarize_tool_result(item["result"]),
                            result_preview=_build_tool_result_preview(item["result"]),
                        )
                        for item in invocations
                    ],
                    affected_task_ids=result.affected_task_ids,
                ),
            )
        return result

    async def render_notification(
        self,
        *,
        context: CommunicationContext,
        candidates: list[NotificationCandidate],
        on_trace: LlmTraceCallback | None = None,
        on_tool_call: ToolCallCallback | None = None,
    ) -> str:
        prompt_request = build_notification_prompt_request(context=context, candidates=candidates)
        trace_id = f"llm-notif-{uuid4().hex[:8]}"
        candidate_payload = build_notification_candidates_payload(candidates)["notification_candidates"]
        if on_trace is not None:
            await _emit_trace(
                on_trace,
                LlmTraceRecord(
                    trace_id=trace_id,
                    source="notification",
                    phase="request_built",
                    prompt_sections=prompt_request.prompt_sections,
                    messages=prompt_request.messages,
                    notification_candidates=candidate_payload,
                    notification_key_task_id=prompt_request.notification_key_task_id,
                    notification_relevant_task_ids=prompt_request.notification_relevant_task_ids,
                    notification_recent_chat_turn_count=prompt_request.notification_recent_chat_turn_count,
                    affected_task_ids=sorted({candidate.task_id for candidate in candidates}),
                ),
            )
        reply_text, _ = await self._provider.run_tool_calling(
            messages=prompt_request.messages,
            tools=[],
            tool_runner=_unused_tool_runner,
        )
        if on_trace is not None:
            await _emit_trace(
                on_trace,
                LlmTraceRecord(
                    trace_id=trace_id,
                    source="notification",
                    phase="response_completed",
                    prompt_sections=prompt_request.prompt_sections,
                    messages=prompt_request.messages,
                    reply_text=reply_text,
                    notification_candidates=candidate_payload,
                    notification_key_task_id=prompt_request.notification_key_task_id,
                    notification_relevant_task_ids=prompt_request.notification_relevant_task_ids,
                    notification_recent_chat_turn_count=prompt_request.notification_recent_chat_turn_count,
                    affected_task_ids=sorted({candidate.task_id for candidate in candidates}),
                ),
            )
        return reply_text


def _extract_task_id(result: object) -> str | None:
    task_id = getattr(result, "task_id", None)
    if isinstance(task_id, str):
        return task_id
    if isinstance(result, dict):
        affected_task_ids = result.get("affected_task_ids")
        if isinstance(affected_task_ids, list):
            for item in affected_task_ids:
                if isinstance(item, str):
                    return item
        task = result.get("task")
        task_id = getattr(task, "task_id", None)
        if isinstance(task_id, str):
            return task_id
    return None


async def _unused_tool_runner(name: str, args: dict[str, object]) -> object:
    raise RuntimeError(f"Unexpected tool call during notification rendering: {name}")


async def _emit_trace(callback: LlmTraceCallback, trace: LlmTraceRecord) -> None:
    maybe_awaitable = callback(trace)
    if isawaitable(maybe_awaitable):
        await maybe_awaitable


async def _emit_tool_call_record(
    callback: ToolCallCallback,
    payload: dict[str, object],
) -> None:
    status = str(payload.get("status", "succeeded"))
    result = payload.get("result")
    error_payload = payload.get("error")
    record = ToolCallRecord(
        tool_name=str(payload.get("name", "")),
        args=payload.get("args") if isinstance(payload.get("args"), dict) else {},
        status="failed" if status == "failed" else "succeeded",
        result_summary=_summarize_tool_result(result) if status != "failed" else None,
        result_preview=_build_tool_result_preview(result) if status != "failed" else None,
        error=(
            ToolCallError(
                code=str(error_payload.get("code", "tool_error")),
                message=str(error_payload.get("message", "Tool call failed.")),
            )
            if isinstance(error_payload, dict)
            else None
        ),
        affected_task_ids=[
            task_id for task_id in [_extract_task_id(result)] if task_id
        ],
    )
    maybe_awaitable = callback(record)
    if isawaitable(maybe_awaitable):
        await maybe_awaitable


def _summarize_tool_result(result: object) -> str:
    if isinstance(result, Task):
        return f"{result.title} ({result.task_id}) [{result.status.value}]"
    if isinstance(result, TaskCommand):
        return f"{result.command_type.value} for {result.task_id}"
    if isinstance(result, TaskSummary):
        text = result.conversational_summary or result.operational_summary or result.task_id
        status = result.latest_user_visible_status or "summary"
        return f"{status}: {text}"
    if isinstance(result, dict):
        if isinstance(result.get("task"), Task) and isinstance(result.get("command"), TaskCommand):
            task = result["task"]
            command = result["command"]
            return f"{command.command_type.value} for {task.title} ({task.task_id})"
        if isinstance(result.get("matches"), list):
            matches = result["matches"]
            if not matches:
                return "0 task matches"
            top = ", ".join(
                str(match.get("title") or match.get("task_id") or "task")
                for match in matches[:3]
                if isinstance(match, dict)
            )
            return f"{len(matches)} task matches" + (f": {top}" if top else "")
        if isinstance(result.get("task"), Task):
            task = result["task"]
            runs = result.get("runs")
            sessions = result.get("sessions")
            return (
                f"{task.title} ({task.task_id}) [{task.status.value}]"
                f"; runs={len(runs) if isinstance(runs, list) else 0}"
                f"; sessions={len(sessions) if isinstance(sessions, list) else 0}"
            )
        if isinstance(result.get("summary"), TaskSummary):
            summary = result["summary"]
            text = summary.conversational_summary or summary.operational_summary or summary.task_id
            status = summary.latest_user_visible_status or "summary"
            return f"{status}: {text}"
        keys = sorted(result.keys())
        return "Result keys: " + ", ".join(keys[:5]) if keys else "Empty result"
    preview = _safe_preview_text(result)
    return preview or "No result"


def _build_tool_result_preview(result: object) -> dict[str, object] | None:
    if isinstance(result, Task):
        return {
            "task_id": result.task_id,
            "title": result.title,
            "goal": result.goal,
            "status": result.status.value,
        }
    if isinstance(result, TaskCommand):
        return {
            "command_id": result.command_id,
            "task_id": result.task_id,
            "command_type": result.command_type.value,
            "reason": result.reason,
        }
    if isinstance(result, TaskSummary):
        return {
            "task_id": result.task_id,
            "latest_user_visible_status": result.latest_user_visible_status,
            "conversational_summary": result.conversational_summary,
            "operational_summary": result.operational_summary,
        }
    if isinstance(result, dict):
        return _preview_dict(result)
    preview = _safe_preview_text(result)
    if preview:
        return {"value": preview}
    return None


def _preview_dict(value: dict[str, Any]) -> dict[str, object]:
    preview: dict[str, object] = {}
    for key in sorted(value.keys())[:6]:
        item = value[key]
        if isinstance(item, (str, int, float, bool)) or item is None:
            preview[key] = item
        elif isinstance(item, Task):
            preview[key] = {
                "task_id": item.task_id,
                "title": item.title,
                "status": item.status.value,
            }
        elif isinstance(item, TaskCommand):
            preview[key] = {
                "task_id": item.task_id,
                "command_type": item.command_type.value,
            }
        elif isinstance(item, TaskSummary):
            preview[key] = {
                "task_id": item.task_id,
                "latest_user_visible_status": item.latest_user_visible_status,
                "conversational_summary": item.conversational_summary,
            }
        elif isinstance(item, list):
            preview[key] = f"{len(item)} items"
        elif isinstance(item, dict):
            preview[key] = {"keys": sorted(item.keys())[:5]}
        else:
            text = _safe_preview_text(item)
            preview[key] = text or type(item).__name__
    return preview


def _safe_preview_text(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value[:160]
    try:
        return json.dumps(value, default=str)[:160]
    except TypeError:
        return str(value)[:160]
