from __future__ import annotations

from synopse.infrastructure.llm import OpenAIProvider
from synopse.protocol import NotificationCandidate

from ..context import CommunicationContext
from ..model import CommunicationModelResult, TextDeltaCallback
from ..policies import infer_conversational_act
from ..prompts import build_notification_messages, build_reply_messages
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
    ) -> CommunicationModelResult:
        reply_text, invocations = await self._provider.run_tool_calling(
            messages=build_reply_messages(user_text=user_text, context=context),
            tools=tool_registry.openai_tools,
            tool_runner=lambda name, args: tool_registry.get(name).invoke(**args),
            on_text_delta=on_text_delta,
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

    async def render_notification(
        self,
        *,
        context: CommunicationContext,
        candidates: list[NotificationCandidate],
    ) -> str:
        reply_text, _ = await self._provider.run_tool_calling(
            messages=build_notification_messages(context=context, candidates=candidates),
            tools=[],
            tool_runner=_unused_tool_runner,
        )
        return reply_text


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


async def _unused_tool_runner(name: str, args: dict[str, object]) -> object:
    raise RuntimeError(f"Unexpected tool call during notification rendering: {name}")
