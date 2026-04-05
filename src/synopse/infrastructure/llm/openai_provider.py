from __future__ import annotations

import json
import inspect
from collections.abc import Awaitable, Callable
from typing import Any

from synopse.communication.tools.base import ToolInputError
from synopse.runtime.config import Settings


class OpenAIProvider:
    def __init__(self, settings: Settings, client: Any | None = None) -> None:
        self._settings = settings
        self._client = client if client is not None else self._build_client()

    def _build_client(self) -> Any:
        if not self._settings.openai_api_key:
            raise RuntimeError(
                "OpenAI configuration is required. Set OPENAI_API_KEY before starting Synopse."
            )

        from openai import AsyncOpenAI

        kwargs: dict[str, Any] = {
            "api_key": self._settings.openai_api_key,
            "timeout": self._settings.openai_timeout_seconds,
        }
        if self._settings.openai_base_url:
            kwargs["base_url"] = self._settings.openai_base_url
        return AsyncOpenAI(**kwargs)

    async def _await_if_needed(self, value: Any) -> Any:
        if inspect.isawaitable(value):
            return await value
        return value

    async def create_completion(self, **kwargs: Any) -> Any:
        return await self._await_if_needed(self._client.chat.completions.create(**kwargs))

    async def run_tool_calling(
        self,
        *,
        messages: list[dict[str, object]],
        tools: list[dict[str, object]],
        tool_runner: Callable[[str, dict[str, object]], Awaitable[object]],
        max_rounds: int = 6,
    ) -> tuple[str, list[dict[str, object]]]:
        chat_messages = list(messages)
        invocations: list[dict[str, object]] = []
        for _ in range(max_rounds):
            completion = await self._create_completion(chat_messages, tools=tools)
            message = _get_first_message(completion)
            tool_calls = _extract_tool_calls(message)
            if tool_calls:
                chat_messages.append(_assistant_tool_call_message(message, tool_calls))
                for tool_call in tool_calls:
                    args = _parse_tool_args(tool_call["arguments"])
                    try:
                        result = await tool_runner(str(tool_call["name"]), args)
                    except ToolInputError as exc:
                        chat_messages.append(
                            _tool_message(
                                str(tool_call["id"]),
                                {"error": exc.as_payload()},
                            )
                        )
                        continue
                    invocations.append(
                        {"name": tool_call["name"], "args": args, "result": result}
                    )
                    chat_messages.append(
                        _tool_message(
                            str(tool_call["id"]),
                            _jsonable(result),
                        )
                    )
                continue

            content = _extract_message_content(message)
            if content is not None:
                return content.strip(), invocations

        raise RuntimeError("OpenAI tool-calling loop did not produce a final reply.")

    async def _create_completion(
        self,
        messages: list[dict[str, object]],
        *,
        tools: list[dict[str, object]],
    ) -> Any:
        request_kwargs: dict[str, object] = {
            "model": self._settings.openai_model,
            "messages": messages,
        }
        if tools:
            request_kwargs["tools"] = tools
        return await self.create_completion(**request_kwargs)


def _get_first_message(completion: Any) -> Any:
    choices = _get_value(completion, "choices") or []
    if not choices:
        raise RuntimeError("OpenAI chat completion returned no choices.")
    return _get_value(choices[0], "message")


def _extract_tool_calls(message: Any) -> list[dict[str, object]]:
    calls: list[dict[str, object]] = []
    for item in _get_value(message, "tool_calls") or []:
        function = _get_value(item, "function")
        if _get_value(item, "type") != "function" or function is None:
            continue
        calls.append(
            {
                "id": str(_get_value(item, "id")),
                "name": str(_get_value(function, "name")),
                "arguments": _get_value(function, "arguments", "{}"),
            }
        )
    return calls


def _assistant_tool_call_message(
    message: Any,
    tool_calls: list[dict[str, object]],
) -> dict[str, object]:
    assistant_message: dict[str, object] = {
        "role": "assistant",
        "tool_calls": [
            {
                "id": tool_call["id"],
                "type": "function",
                "function": {
                    "name": tool_call["name"],
                    "arguments": tool_call["arguments"],
                },
            }
            for tool_call in tool_calls
        ],
    }
    content = _extract_message_content(message)
    if content:
        assistant_message["content"] = content
    return assistant_message


def _tool_message(tool_call_id: str, payload: object) -> dict[str, object]:
    return {
        "role": "tool",
        "tool_call_id": tool_call_id,
        "content": json.dumps(payload),
    }


def _extract_message_content(message: Any) -> str | None:
    content = _get_value(message, "content")
    if content is None:
        return None
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        text_parts: list[str] = []
        for part in content:
            text = _get_value(part, "text")
            if isinstance(text, str):
                text_parts.append(text)
        return "".join(text_parts)
    return str(content)


def _parse_tool_args(raw: object) -> dict[str, object]:
    if isinstance(raw, str):
        parsed = json.loads(raw or "{}")
        if isinstance(parsed, dict):
            return parsed
    if isinstance(raw, dict):
        return raw
    return {}


def _jsonable(value: object) -> object:
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        return model_dump(mode="json")
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    return value


def _get_value(value: Any, key: str, default: Any = None) -> Any:
    if isinstance(value, dict):
        return value.get(key, default)
    return getattr(value, key, default)
