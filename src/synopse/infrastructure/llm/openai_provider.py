from __future__ import annotations

import inspect
from typing import Any

from pydantic import BaseModel

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

    async def parse_structured(
        self,
        *,
        instructions: str,
        input_text: str,
        schema: type[BaseModel],
    ) -> BaseModel:
        response = await self._await_if_needed(
            self._client.responses.parse(
                model=self._settings.openai_model,
                instructions=instructions,
                input=input_text,
                text_format=schema,
            )
        )
        parsed = getattr(response, "output_parsed", None)
        if parsed is None:
            raise RuntimeError("OpenAI did not return structured output.")
        return parsed
