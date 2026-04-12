from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import replace
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal, Protocol

from .context import CommunicationContext
from synapse.protocol import NotificationCandidate
from .types import ToolInvocationRecord

if TYPE_CHECKING:
    from .tools import ToolRegistry


TextDeltaCallback = Callable[[str], Awaitable[None] | None]
LlmTraceCallback = Callable[["LlmTraceRecord"], Awaitable[None] | None]
ToolCallCallback = Callable[["ToolCallRecord"], Awaitable[None] | None]


@dataclass(slots=True)
class ToolCall:
    name: str
    args: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class CommunicationModelResult:
    reply_text: str
    tool_invocations: list[ToolInvocationRecord] = field(default_factory=list)
    affected_task_ids: list[str] = field(default_factory=list)
    conversational_act: str | None = None


@dataclass(slots=True)
class LlmToolInvocationTrace:
    tool_name: str
    args: dict[str, Any] = field(default_factory=dict)
    result_summary: str | None = None
    result_preview: dict[str, object] | None = None


@dataclass(slots=True)
class ToolCallError:
    code: str
    message: str


@dataclass(slots=True)
class ToolCallRecord:
    tool_name: str
    args: dict[str, Any] = field(default_factory=dict)
    status: Literal["succeeded", "failed"] = "succeeded"
    result_summary: str | None = None
    result_preview: dict[str, object] | None = None
    error: ToolCallError | None = None
    affected_task_ids: list[str] = field(default_factory=list)
    request_id: str | None = None

    def with_request_id(self, request_id: str) -> "ToolCallRecord":
        return replace(self, request_id=request_id)


@dataclass(slots=True)
class LlmTraceRecord:
    trace_id: str
    source: Literal["message", "notification"]
    phase: Literal["request_built", "response_completed"]
    prompt_sections: list[str] = field(default_factory=list)
    messages: list[dict[str, object]] = field(default_factory=list)
    request_id: str | None = None
    user_text: str | None = None
    reply_text: str | None = None
    available_tools: list[str] = field(default_factory=list)
    notification_candidates: list[dict[str, object]] = field(default_factory=list)
    notification_key_task_id: str | None = None
    notification_relevant_task_ids: list[str] = field(default_factory=list)
    notification_recent_chat_turn_count: int = 0
    tool_invocations: list[LlmToolInvocationTrace] = field(default_factory=list)
    affected_task_ids: list[str] = field(default_factory=list)

    def with_request_id(self, request_id: str) -> "LlmTraceRecord":
        return replace(self, request_id=request_id)


class CommunicationModel(Protocol):
    async def respond(
        self,
        *,
        user_text: str,
        context: CommunicationContext,
        tool_registry: "ToolRegistry",
        on_text_delta: TextDeltaCallback | None = None,
        on_trace: LlmTraceCallback | None = None,
        on_tool_call: ToolCallCallback | None = None,
    ) -> CommunicationModelResult:
        ...

    async def render_notification(
        self,
        *,
        context: CommunicationContext,
        candidates: list[NotificationCandidate],
        on_trace: LlmTraceCallback | None = None,
        on_tool_call: ToolCallCallback | None = None,
    ) -> str:
        ...
