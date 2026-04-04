from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from runtime.infrastructure.config import Settings
from runtime.llm.errors import LLMConfigurationError, LLMInvocationError


class OpenAIProvider:
    def __init__(self, settings: Settings, client: Any | None = None) -> None:
        self._settings = settings
        self._client = client if client is not None else self._build_client()

    def _build_client(self) -> Any | None:
        if not self._settings.openai_api_key:
            raise LLMConfigurationError(
                "OpenAI configuration is required. Set OPENAI_API_KEY before starting Synopse."
            )

        from openai import OpenAI

        kwargs: dict[str, Any] = {
            "api_key": self._settings.openai_api_key,
            "timeout": self._settings.openai_timeout_seconds,
        }
        if self._settings.openai_base_url:
            kwargs["base_url"] = self._settings.openai_base_url
        return OpenAI(**kwargs)

    def _require_client(self) -> Any:
        if self._client is None:
            raise LLMConfigurationError("OpenAI provider is not available.")
        return self._client

    def parse_structured(
        self,
        *,
        instructions: str,
        input_text: str,
        schema: type[BaseModel],
    ) -> BaseModel:
        client = self._require_client()
        try:
            response = client.responses.parse(
                model=self._settings.openai_model,
                instructions=instructions,
                input=input_text,
                text_format=schema,
            )
        except Exception as exc:  # pragma: no cover
            raise LLMInvocationError(f"OpenAI structured call failed: {exc}") from exc

        parsed = getattr(response, "output_parsed", None)
        if parsed is None:
            raise LLMInvocationError("OpenAI did not return a structured output payload.")
        return parsed

    def render_text(self, *, instructions: str, input_text: str) -> str:
        client = self._require_client()
        try:
            response = client.responses.create(
                model=self._settings.openai_model,
                instructions=instructions,
                input=input_text,
            )
        except Exception as exc:  # pragma: no cover
            raise LLMInvocationError(f"OpenAI text generation failed: {exc}") from exc

        output_text = getattr(response, "output_text", None)
        if not output_text:
            raise LLMInvocationError("OpenAI did not return any output text.")
        return str(output_text).strip()
