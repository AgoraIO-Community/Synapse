from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from synopse.blackboard import BlackboardStore

from .control_task import ControlTaskTool
from .create_task import CreateTaskTool
from .list_tasks import ListTasksTool
from .query_task_detail import QueryTaskDetailTool
from .query_task_summary import QueryTaskSummaryTool
from .update_task import UpdateTaskTool


@dataclass(slots=True)
class ToolRegistry:
    tools: dict[str, Any]

    def get(self, name: str) -> Any:
        return self.tools[name]

    @property
    def names(self) -> list[str]:
        return sorted(self.tools.keys())


def build_default_tool_registry(store: BlackboardStore) -> ToolRegistry:
    return ToolRegistry(
        tools={
            "control_task": ControlTaskTool(store),
            "create_task": CreateTaskTool(store),
            "list_tasks": ListTasksTool(store),
            "query_task_detail": QueryTaskDetailTool(store),
            "query_task_summary": QueryTaskSummaryTool(store),
            "update_task": UpdateTaskTool(store),
        }
    )
