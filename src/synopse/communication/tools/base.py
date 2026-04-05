from __future__ import annotations

from typing import Any, Protocol


class ToolInputError(ValueError):
    def __init__(self, message: str, *, code: str = "invalid_tool_input") -> None:
        super().__init__(message)
        self.code = code

    def as_payload(self) -> dict[str, str]:
        return {
            "code": self.code,
            "message": str(self),
        }


class Tool(Protocol):
    name: str

    async def __call__(self, **kwargs: Any) -> Any:
        ...
