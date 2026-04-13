from __future__ import annotations


def build_normal_reply_task_prompt(*, user_text: str, available_tools: list[str]) -> str:
    tool_list = ", ".join(available_tools)
    return "\n".join(
        [
            "You are handling a normal user message.",
            f"The latest user message is: {user_text}",
            f"Available tools: {tool_list}",
            "When the user wants fact-checking, current external information, or other live verification, do not answer from unsupported guesswork.",
            "If the request is specific enough to execute, prefer create_task. If a required detail is missing, ask one short clarification first.",
            "Use tool calling only when needed, then produce one natural final reply.",
        ]
    )
