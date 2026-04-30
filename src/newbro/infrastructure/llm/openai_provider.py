from __future__ import annotations

import json
import inspect
from collections.abc import Awaitable, Callable
from typing import Any

from newbro.communication.tools.base import ToolInputError
from newbro.runtime.config import Settings

ToolCallEventCallback = Callable[[dict[str, object]], Awaitable[None] | None]


class OpenAIProvider:
    def __init__(self, settings: Settings, client: Any | None = None) -> None:
        self._settings = settings
        self._client = client if client is not None else self._build_client()

    def _build_client(self) -> Any:
        if not self._settings.openai_api_key:
            raise RuntimeError(
                "OpenAI configuration is required. Set OPENAI_API_KEY before starting Newbro."
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
        on_text_delta: Callable[[str], Awaitable[None] | None] | None = None,
        on_tool_call: ToolCallEventCallback | None = None,
    ) -> tuple[str, list[dict[str, object]]]:
        if on_text_delta is not None:
            return await self._run_tool_calling_streamed(
                messages=messages,
                tools=tools,
                tool_runner=tool_runner,
                max_rounds=max_rounds,
                on_text_delta=on_text_delta,
                on_tool_call=on_tool_call,
            )

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
                        await _emit_tool_call(
                            on_tool_call,
                            {
                                "name": str(tool_call["name"]),
                                "args": args,
                                "status": "failed",
                                "error": exc.as_payload(),
                            },
                        )
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
                    await _emit_tool_call(
                        on_tool_call,
                        {
                            "name": str(tool_call["name"]),
                            "args": args,
                            "status": "succeeded",
                            "result": result,
                        },
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

    async def _run_tool_calling_streamed(
        self,
        *,
        messages: list[dict[str, object]],
        tools: list[dict[str, object]],
        tool_runner: Callable[[str, dict[str, object]], Awaitable[object]],
        max_rounds: int,
        on_text_delta: Callable[[str], Awaitable[None] | None],
        on_tool_call: ToolCallEventCallback | None,
    ) -> tuple[str, list[dict[str, object]]]:
        chat_messages = list(messages)
        invocations: list[dict[str, object]] = []
        for _ in range(max_rounds):
            text_chunks: list[str] = []
            tool_call_chunks: dict[int, dict[str, object]] = {}

            async for chunk in self._iter_completion_chunks(chat_messages, tools=tools):
                delta = _extract_chunk_delta(chunk)
                if delta is None:
                    continue
                text = _extract_delta_content(delta)
                if text:
                    text_chunks.append(text)
                for tool_call_delta in _extract_delta_tool_calls(delta):
                    _accumulate_tool_call_delta(tool_call_chunks, tool_call_delta)

            tool_calls = _finalize_tool_call_chunks(tool_call_chunks)
            if tool_calls:
                chat_messages.append(
                    _assistant_tool_call_message_from_parts("".join(text_chunks), tool_calls)
                )
                for tool_call in tool_calls:
                    args = _parse_tool_args(tool_call["arguments"])
                    try:
                        result = await tool_runner(str(tool_call["name"]), args)
                    except ToolInputError as exc:
                        await _emit_tool_call(
                            on_tool_call,
                            {
                                "name": str(tool_call["name"]),
                                "args": args,
                                "status": "failed",
                                "error": exc.as_payload(),
                            },
                        )
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
                    await _emit_tool_call(
                        on_tool_call,
                        {
                            "name": str(tool_call["name"]),
                            "args": args,
                            "status": "succeeded",
                            "result": result,
                        },
                    )
                    chat_messages.append(
                        _tool_message(
                            str(tool_call["id"]),
                            _jsonable(result),
                        )
                    )
                continue

            content = "".join(text_chunks)
            if content:
                for chunk in text_chunks:
                    maybe_awaitable = on_text_delta(chunk)
                    if inspect.isawaitable(maybe_awaitable):
                        await maybe_awaitable
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

    async def _iter_completion_chunks(
        self,
        messages: list[dict[str, object]],
        *,
        tools: list[dict[str, object]],
    ):
        request_kwargs: dict[str, object] = {
            "model": self._settings.openai_model,
            "messages": messages,
            "stream": True,
        }
        if tools:
            request_kwargs["tools"] = tools

        stream = await self.create_completion(**request_kwargs)
        if hasattr(stream, "__aenter__") and hasattr(stream, "__aexit__"):
            async with stream as entered:
                async for chunk in entered:
                    yield chunk
            return

        try:
            async for chunk in stream:
                yield chunk
        finally:
            close = getattr(stream, "aclose", None)
            if callable(close):
                await self._await_if_needed(close())


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
    return _assistant_tool_call_message_from_parts(_extract_message_content(message), tool_calls)


def _assistant_tool_call_message_from_parts(
    content: str | None,
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
                continue
            text_value = _get_value(text, "value")
            if isinstance(text_value, str):
                text_parts.append(text_value)
        return "".join(text_parts)
    return str(content)


def _extract_chunk_delta(chunk: Any) -> Any | None:
    choices = _get_value(chunk, "choices") or []
    if not choices:
        return None
    return _get_value(choices[0], "delta")


def _extract_delta_content(delta: Any) -> str:
    content = _get_value(delta, "content")
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        text_parts: list[str] = []
        for part in content:
            text = _get_value(part, "text")
            if isinstance(text, str):
                text_parts.append(text)
                continue
            text_value = _get_value(text, "value")
            if isinstance(text_value, str):
                text_parts.append(text_value)
        return "".join(text_parts)
    return str(content)


def _extract_delta_tool_calls(delta: Any) -> list[dict[str, object]]:
    tool_calls: list[dict[str, object]] = []
    for item in _get_value(delta, "tool_calls") or []:
        tool_calls.append(
            {
                "index": int(_get_value(item, "index", 0) or 0),
                "id": _get_value(item, "id"),
                "type": _get_value(item, "type"),
                "name": _get_value(_get_value(item, "function"), "name"),
                "arguments": _get_value(_get_value(item, "function"), "arguments"),
            }
        )
    return tool_calls


def _accumulate_tool_call_delta(
    buffers: dict[int, dict[str, object]],
    delta: dict[str, object],
) -> None:
    index = int(delta.get("index", 0) or 0)
    item = buffers.setdefault(
        index,
        {
            "id": "",
            "name": "",
            "arguments": "",
            "type": "function",
        },
    )
    item["id"] = _append_fragment(str(item["id"]), delta.get("id"))
    item["name"] = _append_fragment(str(item["name"]), delta.get("name"))
    item["arguments"] = _append_fragment(str(item["arguments"]), delta.get("arguments"))
    item_type = delta.get("type")
    if isinstance(item_type, str) and item_type:
        item["type"] = item_type


def _finalize_tool_call_chunks(
    buffers: dict[int, dict[str, object]],
) -> list[dict[str, object]]:
    tool_calls: list[dict[str, object]] = []
    for index in sorted(buffers):
        item = buffers[index]
        if item["type"] != "function" or not item["name"]:
            continue
        tool_calls.append(
            {
                "id": str(item["id"] or f"call-{index}"),
                "name": str(item["name"]),
                "arguments": str(item["arguments"] or "{}"),
            }
        )
    return tool_calls


def _append_fragment(existing: str, fragment: object) -> str:
    if not isinstance(fragment, str) or not fragment:
        return existing
    if not existing:
        return fragment
    if fragment.startswith(existing):
        return fragment
    if existing.endswith(fragment):
        return existing
    return existing + fragment


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


async def _emit_tool_call(
    callback: ToolCallEventCallback | None,
    payload: dict[str, object],
) -> None:
    if callback is None:
        return
    maybe_awaitable = callback(payload)
    if inspect.isawaitable(maybe_awaitable):
        await maybe_awaitable
