from __future__ import annotations

from uuid import uuid4

from synopse.blackboard import BlackboardStore
from synopse.protocol import ExecutionMode, MutationType, Task, TaskExecutionMode, TaskMutation

from .base import ToolInputError


class CreateTaskTool:
    name = "create_task"

    def __init__(
        self,
        store: BlackboardStore,
        *,
        valid_executor_types: list[str],
        default_executor_type: str,
    ) -> None:
        self._store = store
        self._valid_executor_types = list(valid_executor_types)
        self._default_executor_type = default_executor_type

    @property
    def valid_executor_types(self) -> list[str]:
        return list(self._valid_executor_types)

    async def __call__(
        self,
        *,
        title: str,
        goal: str,
        preferred_executor: str | None = None,
        requires_confirmation: bool = False,
        mock_safe: bool = False,
    ) -> Task:
        resolved_executor = preferred_executor or self._default_executor_type
        if resolved_executor not in self._valid_executor_types:
            allowed = ", ".join(self._valid_executor_types)
            raise ToolInputError(
                f"Invalid create_task preferred_executor '{resolved_executor}'. Use one of: {allowed}.",
                code="invalid_executor_type",
            )
        if resolved_executor == "mock" and not mock_safe:
            raise ToolInputError(
                "A real executor is required for normal task execution, but only the mock executor is available right now.",
                code="real_executor_required",
            )

        task_id = f"task-{uuid4().hex[:8]}"
        task = Task(
            task_id=task_id,
            root_task_id=task_id,
            title=title,
            goal=goal,
            preferred_executor=resolved_executor,
            requires_confirmation=requires_confirmation,
            metadata={"mock_safe": True} if mock_safe else {},
        )
        await self._store.put_task(task)
        await self._store.put_execution_mode(
            TaskExecutionMode(
                task_id=task_id,
                mode=ExecutionMode.UNDECIDED,
            )
        )
        await self._store.append_mutation(
            TaskMutation(
                mutation_id=f"mut-{uuid4().hex[:8]}",
                task_id=task_id,
                mutation_type=MutationType.CREATE,
                patch={
                    "title": title,
                    "goal": goal,
                    "preferred_executor": resolved_executor,
                    "mock_safe": mock_safe,
                },
                created_by="communication_brain",
            )
        )
        saved = await self._store.get_task(task_id)
        return saved or task
