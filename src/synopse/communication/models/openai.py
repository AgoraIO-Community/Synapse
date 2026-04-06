from __future__ import annotations

import json

from synopse.infrastructure.llm import OpenAIProvider
from synopse.protocol import NotificationCandidate

from ..context import CommunicationContext
from ..model import CommunicationModelResult, TextDeltaCallback
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
        on_text_delta: TextDeltaCallback | None = None,
    ) -> CommunicationModelResult:
        reply_text, invocations = await self._provider.run_tool_calling(
            messages=_build_messages(user_text, context),
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
            messages=_build_notification_messages(context, candidates),
            tools=[],
            tool_runner=_unused_tool_runner,
        )
        return reply_text


def _build_messages(user_text: str, context: CommunicationContext) -> list[dict[str, object]]:
    return [
        _message("system", _build_instructions(user_text, context.available_tools)),
        _message("system", _build_tool_policy(context)),
        _message("system", _build_examples(context)),
        _message("system", json.dumps(_build_runtime_context(context))),
        *[_message(entry.role, entry.text) for entry in context.recent_history],
    ]


def _build_instructions(user_text: str, available_tools: list[str]) -> str:
    tool_list = ", ".join(available_tools)
    return "\n".join(
        [
            "You are the Communication Brain for Synopse.",
            "Replay the prior user and assistant messages as the authoritative recent conversation history for this session.",
            f"The latest user message is: {user_text}",
            "Reply in the same language as the latest user message unless the user explicitly asks for another language.",
            "Keep replies short, spoken-language friendly, and natural for voice output.",
            "Prefer action-commitment phrasing over system-state announcements.",
            "Do not expose internal tool names, command schemas, or runtime vocabulary unless the user explicitly asks for them.",
            "Do not emit mechanical text like 'task created successfully' or 'command applied'.",
            f"Available tools: {tool_list}",
            "Use tool calling only when needed, then produce one natural final reply.",
        ]
    )


def _build_tool_policy(context: CommunicationContext) -> str:
    lines = [
        "Tool-selection policy:",
        "- create_task: brand-new work or actionable user requests that should become a task.",
        "- update_task: change core structured task fields such as title, goal, priority, executor preference, or latest_instruction.",
        "- add_task_note: append extra user context, examples, preferences, or clarifications to an existing task.",
        "- add_constraint: append execution constraints such as deadlines, formatting rules, do-not-send, forbidden actions, or required approach.",
        "- control_task: pause, resume, cancel, retry, or preempt a task.",
        "- list_tasks: resolve references like 'that one', 'the email task', or 'the last task' before a write or query when the target is uncertain.",
        "- query_task_summary: answer user-facing progress questions.",
        "- query_task_detail: answer deeper status questions that need more execution detail.",
        "Decision rules:",
        "- Default to the task model for actionable requests, even when the user phrases them as a question.",
        "- Only clear social chat, subjective/persona questions, and Synopse meta questions should stay as pure chat.",
        "- Requests to inspect the user's machine, inspect the current repo/workspace, run commands, or read the environment should normally become tasks.",
        "- For existing-task writes or queries, if the target is uncertain, call list_tasks first.",
        "- Prefer add_task_note or add_constraint over update_task when the user is appending context rather than changing the task's core identity.",
        "- Use at most one write tool unless a read-then-write step is necessary.",
        "- When using control_task, command_type must exactly match the schema value such as 'resume_task', not shortened verbs like 'resume'.",
    ]
    if context.executor_runtime.has_real_executor:
        lines.append(
            "- At least one real executor is available, so normal actionable requests should usually become tasks."
        )
    else:
        lines.append(
            "- Only the mock executor is available. Do not create ordinary work tasks unless the user explicitly asks for a mock or simulated task."
        )
        lines.append(
            "- When only the mock executor is available, normal task requests should be blocked with a clear natural-language explanation instead of fake task creation."
        )
        lines.append(
            "- Do not reply with generic manual tips unless the user explicitly asks for instructions."
        )
    lines.append(
        "- Only set create_task.mock_safe=true when the user explicitly wants a mock, simulated, or record-only task."
    )
    return "\n".join(lines)


def _build_examples(context: CommunicationContext) -> str:
    lines = [
        "Examples:",
        "User: 帮我查一下明天上海到北京的航班",
        "Preferred tool: create_task",
        "Preferred reply style: 好，我先查一下。",
        "User: 给刚才那个邮件任务补一句，语气再简短一点",
        "Preferred tool: add_task_note or update_task when the target is clear; list_tasks first when target is not clear.",
        "Preferred reply style: 好，我补上这条要求。",
        "User: 那个任务先别发出去",
        "Preferred tool: add_constraint when the target is clear; otherwise list_tasks first.",
        "Preferred reply style: 好，这个我先按住，不发出去。",
        "User: 那个任务现在到哪了",
        "Preferred tool: query_task_summary when target is clear; otherwise list_tasks first.",
        "Preferred reply style: 这个现在已经处理到……",
        "User: 你觉得我今天状态怎么样",
        "Preferred tool: no tool.",
        "Preferred reply style: 直接自然回答，不要硬转成任务。",
        "User: Can you help me analyze this bug?",
        "Preferred tool: create_task",
        "Preferred reply style: Sure, I'll dig into it.",
    ]
    if context.executor_runtime.has_real_executor:
        lines.extend(
            [
                "User: check my pc cpu usage",
                "Preferred tool: create_task",
                "Preferred reply style: Okay, I'll check that.",
            ]
        )
    else:
        lines.extend(
            [
                "User: check my pc cpu usage",
                "Preferred tool: no tool or create_task rejected in-band because no real executor is available.",
                "Preferred reply style: I can't actually check your machine right now because I don't have a real executor connected.",
                "User: help me draft an email reply",
                "Preferred tool: no tool or create_task rejected in-band because only the mock executor is available.",
                "Preferred reply style: I can't actually take that on right now because I don't have a real executor connected.",
            ]
        )
    return "\n".join(lines)


def _build_runtime_context(context: CommunicationContext) -> dict[str, object]:
    return {
        "conversation_id": context.conversation_id,
        "active_tasks": [
            {
                "task_id": task.task_id,
                "title": task.title,
                "goal": task.goal,
                "status": task.status,
                "priority": task.priority,
                "latest_instruction": task.latest_instruction,
                "conversational_summary": task.conversational_summary,
                "latest_user_visible_status": task.latest_user_visible_status,
                "note_count": task.note_count,
                "constraint_count": task.constraint_count,
            }
            for task in context.active_tasks
        ],
        "recent_tasks": [
            {
                "task_id": task.task_id,
                "title": task.title,
                "goal": task.goal,
                "status": task.status,
                "priority": task.priority,
                "latest_instruction": task.latest_instruction,
                "conversational_summary": task.conversational_summary,
                "latest_user_visible_status": task.latest_user_visible_status,
                "note_count": task.note_count,
                "constraint_count": task.constraint_count,
            }
            for task in context.recent_tasks
        ],
        "executor_runtime": {
            "has_real_executor": context.executor_runtime.has_real_executor,
            "available_executor_types": context.executor_runtime.available_executor_types,
            "default_executor_type": context.executor_runtime.default_executor_type,
            "executors": context.executor_runtime.executors,
        },
        "available_tools": context.available_tools,
    }


def _build_notification_messages(
    context: CommunicationContext,
    candidates: list[NotificationCandidate],
) -> list[dict[str, object]]:
    return [
        _message(
            "system",
            "\n".join(
                [
                    "You are the Communication Brain for Synopse.",
                    "Generate one proactive assistant update from the selected notification facts.",
                    "Keep the same language and persona as the recent visible conversation.",
                    "Keep it concise, spoken-language friendly, and natural.",
                    "Do not mention internal terms like notification candidate, task id, or runtime state.",
                    "Do not use tools.",
                ]
            ),
        ),
        _message(
            "system",
            json.dumps(_build_runtime_context(context)),
        ),
        _message(
            "system",
            json.dumps(
                {
                    "notification_candidates": [
                        {
                            "candidate_type": candidate.candidate_type.value,
                            "task_id": candidate.task_id,
                            "summary_short": candidate.summary_short,
                            "priority": candidate.priority.value,
                        }
                        for candidate in candidates
                    ]
                }
            ),
        ),
        *[_message(entry.role, entry.text) for entry in context.recent_history],
    ]


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


async def _unused_tool_runner(name: str, args: dict[str, object]) -> object:
    raise RuntimeError(f"Unexpected tool call during notification rendering: {name}")
