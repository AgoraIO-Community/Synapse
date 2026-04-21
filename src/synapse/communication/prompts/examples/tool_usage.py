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
        "User: Forget it.",
        "Preferred tool: control_task with cancel_task when one active target is clear; otherwise ask which task to cancel.",
        "Preferred reply style: Okay, I won't continue with that.",
        "User: It should be Shanghai.",
        "Preferred tool: apply the correction to the focused task or task bundle when the corrected field is clear; otherwise ask one short clarification.",
        "Preferred reply style: Do you mean the destination should be Shanghai instead?",
        "User: Where is that task now?",
        "Preferred tool: query_task_summary when target is clear; otherwise list_tasks first.",
        "Preferred reply style: Here's the latest progress.",
        "User: (pending interaction request: permission) Confirm execution.",
        "Preferred tool: resolve_interaction_request with action='approve' when one pending request is clearly in focus.",
        "Preferred reply style: Okay, I'll continue.",
        "User: (pending interaction request: question) The path is /tmp/report.csv.",
        "Preferred tool: resolve_interaction_request with action='answer' and answer_text set to the user's answer.",
        "Preferred reply style: Okay, I'll continue with that answer.",
        "User: How do I seem today?",
        "Preferred tool: no tool.",
        "Preferred reply style: Answer naturally without forcing it into a task.",
        "User: (active: 'binary tree demo', 'draw a cat') Change it to a red-black tree.",
        "Preferred tool: update_task with task_id of the binary tree task. Same domain. NOT the cat task.",
        "User: (active: 'sorting demo', 'REST API') Change it.",
        "Preferred tool: no tool. Ambiguous and unspecified. Ask which task and what to change.",
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
