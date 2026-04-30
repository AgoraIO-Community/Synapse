from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
import inspect
from typing import Any

from ..context import CommunicationContext
from ..model import (
    CommunicationModelResult,
    LlmTraceCallback,
    TextDeltaCallback,
    ToolCall,
    ToolCallCallback,
    ToolCallError,
    ToolCallRecord,
)
from ..policies import infer_conversational_act, render_reply
from ..tools import ToolRegistry
from ..types import ToolInvocationRecord
from ..tools.base import ToolInputError
from newbro.protocol import NotificationCandidate


@dataclass(slots=True)
class ScriptedPlan:
    tool_calls: list[ToolCall] = field(default_factory=list)
    conversational_act: str | None = None
    reply_override: str | None = None


class ScriptedCommunicationModel:
    def __init__(
        self,
        scripted: dict[
            str,
            ScriptedPlan | Callable[[CommunicationContext], ScriptedPlan],
        ],
    ) -> None:
        self._scripted = scripted

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
        if user_text in self._scripted:
            selected = self._scripted[user_text]
        else:
            selected = self._scripted["__default__"]
        if callable(selected):
            plan = selected(context)
        else:
            plan = selected

        tool_invocations: list[ToolInvocationRecord] = []
        affected_task_ids: list[str] = []
        tool_results: dict[str, object] = {}
        for call in plan.tool_calls:
            tool = tool_registry.get(call.name)
            try:
                result = await tool.invoke(**call.args)
            except ToolInputError as exc:
                await _emit_tool_call(
                    on_tool_call,
                    ToolCallRecord(
                        tool_name=call.name,
                        args=call.args,
                        status="failed",
                        error=ToolCallError(code=exc.code, message=str(exc)),
                    ),
                )
                raise
            except Exception as exc:
                await _emit_tool_call(
                    on_tool_call,
                    ToolCallRecord(
                        tool_name=call.name,
                        args=call.args,
                        status="failed",
                        error=ToolCallError(code="tool_error", message=str(exc) or "Tool call failed."),
                    ),
                )
                raise
            tool_results[call.name] = result
            tool_invocations.append(
                ToolInvocationRecord(tool_name=call.name, args=call.args, result=result)
            )
            task_id = _extract_task_id(result)
            if task_id and task_id not in affected_task_ids:
                affected_task_ids.append(task_id)
            await _emit_tool_call(
                on_tool_call,
                ToolCallRecord(
                    tool_name=call.name,
                    args=call.args,
                    status="succeeded",
                    affected_task_ids=[task_id] if task_id else [],
                ),
            )

        reply_text = render_reply(
            plan.conversational_act or infer_conversational_act(tool_invocations, ""),
            tool_results=tool_results,
            reply_override=plan.reply_override,
        )
        if on_text_delta is not None and reply_text:
            maybe_awaitable = on_text_delta(reply_text)
            if inspect.isawaitable(maybe_awaitable):
                await maybe_awaitable
        return CommunicationModelResult(
            reply_text=reply_text,
            tool_invocations=tool_invocations,
            affected_task_ids=affected_task_ids,
            conversational_act=plan.conversational_act
            or infer_conversational_act(tool_invocations, reply_text),
        )

    async def render_notification(
        self,
        *,
        context: CommunicationContext,
        candidates: list[NotificationCandidate],
        on_trace: LlmTraceCallback | None = None,
        on_tool_call: ToolCallCallback | None = None,
    ) -> str:
        if not candidates:
            return "I have an update."
        if len(candidates) == 1:
            return candidates[0].summary_short
        if all(candidate.candidate_type.value == "completed" for candidate in candidates):
            return f"I finished {len(candidates)} tasks."
        joined = "; ".join(candidate.summary_short for candidate in candidates)
        return joined


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


async def _emit_tool_call(
    callback: ToolCallCallback | None,
    record: ToolCallRecord,
) -> None:
    if callback is None:
        return
    maybe_awaitable = callback(record)
    if inspect.isawaitable(maybe_awaitable):
        await maybe_awaitable
