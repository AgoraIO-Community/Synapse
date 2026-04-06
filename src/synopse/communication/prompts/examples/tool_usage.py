from __future__ import annotations

from synopse.communication.context import CommunicationContext


def build_tool_usage_examples_prompt(context: CommunicationContext) -> str:
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
