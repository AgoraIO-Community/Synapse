from __future__ import annotations


def build_normal_reply_task_prompt(*, user_text: str, available_tools: list[str]) -> str:
    tool_list = ", ".join(available_tools)
    return "\n".join(
        [
            "You are handling a normal user message.",
            f"The latest user message is: {user_text}",
            f"Available tools: {tool_list}",
            "When the user wants fact-checking, current external information, or other live verification, do not answer from unsupported guesswork.",
            "Use focused_tasks and recent task context for short follow-up corrections and control turns.",
            "If a short correction does not clearly map to one field or slot, ask one short clarification instead of guessing.",
            "If the user is clearly stopping an existing task with casual language like 'forget it' or 'never mind', treat that as task control rather than small talk.",
            "If the request is specific enough to execute, prefer create_task. If a required detail is missing, ask one short clarification first.",
            "Use tool calling only when needed, then produce one natural final reply.",
        ]
    )
