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
class ToolSpec:
    name: str
    description: str
    input_schema: dict[str, object]
    handler: Any

    async def invoke(self, **kwargs: Any) -> Any:
        return await self.handler(**kwargs)

    async def __call__(self, **kwargs: Any) -> Any:
        return await self.invoke(**kwargs)


@dataclass(slots=True)
class ToolRegistry:
    tools: dict[str, ToolSpec]

    def get(self, name: str) -> ToolSpec:
        return self.tools[name]

    @property
    def names(self) -> list[str]:
        return sorted(self.tools.keys())

    @property
    def openai_tools(self) -> list[dict[str, object]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": spec.name,
                    "description": spec.description,
                    "parameters": spec.input_schema,
                },
            }
            for spec in self.tools.values()
        ]


def build_default_tool_registry(
    store: BlackboardStore,
    *,
    executor_types: list[str] | None = None,
) -> ToolRegistry:
    resolved_executor_types = sorted(set(executor_types or ["mock"]))
    create_task = CreateTaskTool(store, valid_executor_types=resolved_executor_types)
    control_task = ControlTaskTool(store)
    list_tasks = ListTasksTool(store)
    query_task_detail = QueryTaskDetailTool(store)
    query_task_summary = QueryTaskSummaryTool(store)
    update_task = UpdateTaskTool(store)
    return ToolRegistry(
        tools={
            "control_task": ToolSpec(
                name="control_task",
                description="Pause, cancel, retry, resume, or preempt a task.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "command_type": {
                            "type": "string",
                            "enum": control_task.allowed_command_types,
                        },
                        "task_id": {"type": ["string", "null"]},
                        "reference": {"type": ["string", "null"]},
                        "payload": {"type": "object"},
                        "reason": {"type": ["string", "null"]},
                    },
                    "required": ["command_type"],
                    "additionalProperties": False,
                },
                handler=control_task,
            ),
            "create_task": ToolSpec(
                name="create_task",
                description="Create a new task on the blackboard.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "goal": {"type": "string"},
                        "preferred_executor": {
                            "anyOf": [
                                {"type": "string", "enum": create_task.valid_executor_types},
                                {"type": "null"},
                            ]
                        },
                        "requires_confirmation": {"type": "boolean"},
                    },
                    "required": ["title", "goal"],
                    "additionalProperties": False,
                },
                handler=create_task,
            ),
            "list_tasks": ToolSpec(
                name="list_tasks",
                description="List tasks, optionally filtered by a text query.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "query": {"type": ["string", "null"]},
                    },
                    "additionalProperties": False,
                },
                handler=list_tasks,
            ),
            "query_task_detail": ToolSpec(
                name="query_task_detail",
                description="Inspect one task together with related execution detail.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "task_id": {"type": ["string", "null"]},
                        "reference": {"type": ["string", "null"]},
                    },
                    "additionalProperties": False,
                },
                handler=query_task_detail,
            ),
            "query_task_summary": ToolSpec(
                name="query_task_summary",
                description="Read the user-facing and operational summary for a task.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "task_id": {"type": ["string", "null"]},
                        "reference": {"type": ["string", "null"]},
                    },
                    "additionalProperties": False,
                },
                handler=query_task_summary,
            ),
            "update_task": ToolSpec(
                name="update_task",
                description="Update a task with new instructions or constraints.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "task_id": {"type": ["string", "null"]},
                        "reference": {"type": ["string", "null"]},
                        "patch": {"type": "object"},
                    },
                    "required": ["patch"],
                    "additionalProperties": False,
                },
                handler=update_task,
            ),
        }
    )
