from __future__ import annotations

import json

from pydantic import BaseModel, Field

from synopse.infrastructure.llm import OpenAIProvider

from ..context import CommunicationContext
from ..model import CommunicationDecision, ToolCall


class _DecisionToolCall(BaseModel):
    name: str
    args: dict[str, object] = Field(default_factory=dict)


class _DecisionPayload(BaseModel):
    conversational_act: str
    tool_calls: list[_DecisionToolCall] = Field(default_factory=list)
    reply_override: str | None = None


class OpenAICommunicationModel:
    def __init__(self, provider: OpenAIProvider) -> None:
        self._provider = provider

    async def decide(
        self,
        *,
        user_text: str,
        context: CommunicationContext,
    ) -> CommunicationDecision:
        payload = await self._provider.parse_structured(
            instructions=_build_instructions(context.available_tools),
            input_text=_build_input(user_text, context),
            schema=_DecisionPayload,
        )
        return CommunicationDecision(
            conversational_act=payload.conversational_act,
            tool_calls=[ToolCall(name=item.name, args=item.args) for item in payload.tool_calls],
            reply_override=payload.reply_override,
        )


def _build_instructions(available_tools: list[str]) -> str:
    tool_list = ", ".join(available_tools)
    return "\n".join(
        [
            "You are the Communication Brain for Synopse.",
            "Choose zero or more tool calls, then choose a conversational act.",
            "Do not emit mechanical replies like 'task created successfully'.",
            "Prefer action-commitment phrasing.",
            f"Available tools: {tool_list}",
            "Return only structured output.",
        ]
    )


def _build_input(user_text: str, context: CommunicationContext) -> str:
    history = [
        {"role": entry.role, "text": entry.text, "message_id": entry.message_id}
        for entry in context.recent_history
    ]
    tasks = [
        {
            "task_id": task.task_id,
            "title": task.title,
            "goal": task.goal,
            "status": task.status.value,
            "priority": task.priority,
        }
        for task in context.tasks
    ]
    summaries = {
        task_id: (
            {
                "operational_summary": summary.operational_summary,
                "conversational_summary": summary.conversational_summary,
                "latest_user_visible_status": summary.latest_user_visible_status,
                "needs_user_input": summary.needs_user_input,
            }
            if summary is not None
            else None
        )
        for task_id, summary in context.summaries.items()
    }
    return json.dumps(
        {
            "conversation_id": context.conversation_id,
            "user_text": user_text,
            "history": history,
            "tasks": tasks,
            "summaries": summaries,
            "available_tools": context.available_tools,
        }
    )
