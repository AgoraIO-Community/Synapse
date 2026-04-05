import pytest

from synopse.blackboard import InMemoryBlackboard
from synopse.communication.tools import build_default_tool_registry
from synopse.protocol import TaskCommandType


@pytest.mark.anyio
async def test_create_update_control_and_query_tools():
    store = InMemoryBlackboard()
    registry = build_default_tool_registry(store)

    created = await registry.get("create_task")(
        title="Draft email",
        goal="Draft an email reply",
    )
    assert created.task_id.startswith("task-")

    updated = await registry.get("update_task")(
        task_id=created.task_id,
        patch={"latest_instruction": "Make it shorter."},
    )
    assert updated.latest_instruction == "Make it shorter."

    command = await registry.get("control_task")(
        task_id=created.task_id,
        command_type=TaskCommandType.PAUSE_TASK.value,
    )
    assert command.command_type == TaskCommandType.PAUSE_TASK

    summary = await registry.get("query_task_summary")(task_id=created.task_id)
    assert summary is None

    detail = await registry.get("query_task_detail")(task_id=created.task_id)
    assert detail is not None
    assert detail["task"].task_id == created.task_id
