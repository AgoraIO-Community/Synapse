from __future__ import annotations


class ToolUsagePolicy:
    def __init__(self, tool_names: list[str]) -> None:
        self._tool_names = sorted(tool_names)

    @property
    def available_tools(self) -> list[str]:
        return list(self._tool_names)
