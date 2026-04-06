from __future__ import annotations


def build_normal_reply_task_prompt(*, user_text: str, available_tools: list[str]) -> str:
    tool_list = ", ".join(available_tools)
    return "\n".join(
        [
            "You are handling a normal user message.",
            f"The latest user message is: {user_text}",
            f"Available tools: {tool_list}",
            "Use tool calling only when needed, then produce one natural final reply.",
        ]
    )
