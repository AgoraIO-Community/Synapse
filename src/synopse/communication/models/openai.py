from __future__ import annotations

import json

from synopse.infrastructure.llm import OpenAIProvider

from ..context import CommunicationContext
from ..model import CommunicationModelResult
from ..policies import infer_conversational_act
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
    ) -> CommunicationModelResult:
        reply_text, invocations = await self._provider.run_tool_calling(
            messages=_build_messages(context),
            tools=tool_registry.openai_tools,
            tool_runner=lambda name, args: tool_registry.get(name).invoke(**args),
        )
        tool_invocations = [
            ToolInvocationRecord(tool_name=item["name"], args=item["args"], result=item["result"])
            for item in invocations
        ]
        return CommunicationModelResult(
            reply_text=reply_text,
            tool_invocations=tool_invocations,
            affected_task_ids=[
                task_id
                for task_id in (_extract_task_id(item["result"]) for item in invocations)
                if task_id
            ],
            conversational_act=infer_conversational_act(tool_invocations, reply_text),
        )


def _build_messages(context: CommunicationContext) -> list[dict[str, object]]:
    return [
        _message("system", _build_instructions(context.available_tools)),
        _message("system", json.dumps(_build_runtime_context(context))),
        *[_message(entry.role, entry.text) for entry in context.recent_history],
    ]


def _build_instructions(available_tools: list[str]) -> str:
    tool_list = ", ".join(available_tools)
    return "\n".join(
        [
            "You are the Communication Brain for Synopse.",
            "Replay the prior user and assistant messages as the authoritative recent conversation history for this session.",
            "The runtime context system message contains supplemental state about tasks, summaries, and available tools.",
            "Choose zero or more tool calls, then choose a conversational act.",
            "Do not emit mechanical replies like 'task created successfully'.",
            "Prefer action-commitment phrasing.",
            "When using control_task, command_type must exactly match the schema value such as 'resume_task', not shortened verbs like 'resume'.",
            f"Available tools: {tool_list}",
            "Use tool calling when needed, then produce a natural final reply.",
        ]
    )


def _build_runtime_context(context: CommunicationContext) -> dict[str, object]:
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
    return {
        "conversation_id": context.conversation_id,
        "tasks": tasks,
        "summaries": summaries,
        "available_tools": context.available_tools,
    }


def _message(role: str, text: str) -> dict[str, object]:
    return {"role": role, "content": text}


def _extract_task_id(result: object) -> str | None:
    task_id = getattr(result, "task_id", None)
    if isinstance(task_id, str):
        return task_id
    if isinstance(result, dict):
        task = result.get("task")
        task_id = getattr(task, "task_id", None)
        if isinstance(task_id, str):
            return task_id
    return None
