from __future__ import annotations

from synapse.communication.context import CommunicationContext


def build_tool_usage_examples_prompt(context: CommunicationContext) -> str:
    lines = [
        "Examples:",
        "User: Help me find flights from Shanghai to Beijing tomorrow.",
        "Preferred tool: create_task",
        "Preferred reply style: Okay, I'll check that.",
        "User: What is the weather?",
        "Preferred tool: no tool yet; ask a short clarification for the missing location.",
        "Preferred reply style: Sure, which city should I check?",
        "User: Add one note to that email task: keep the tone shorter.",
        "Preferred tool: add_task_note or update_task when the target is clear; list_tasks first when target is not clear.",
        "Preferred reply style: Okay, I'll add that note.",
        "User: Do not send that task yet.",
        "Preferred tool: add_constraint when the target is clear; otherwise list_tasks first.",
        "Preferred reply style: Okay, I'll hold that for now.",
        "User: Where is that task now?",
        "Preferred tool: query_task_summary when target is clear; otherwise list_tasks first.",
        "Preferred reply style: Here's the latest progress.",
        "User: How do I seem today?",
        "Preferred tool: no tool.",
        "Preferred reply style: Answer naturally without forcing it into a task.",
    ]
    if context.executor_runtime.has_real_executor:
        lines.extend(
            [
                "User: Check my PC CPU usage.",
                "Preferred tool: create_task",
                "Preferred reply style: Okay, I'll check that.",
            ]
        )
    else:
        lines.extend(
            [
                "User: Check my PC CPU usage.",
                "Preferred tool: no tool or create_task rejected in-band because no real executor is available.",
                "Preferred reply style: I can't actually check your machine right now because I don't have a real executor connected.",
            ]
        )
    return "\n".join(lines)
