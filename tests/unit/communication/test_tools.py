import pytest

from synopse.blackboard import InMemoryBlackboard
from synopse.communication.tools import build_default_tool_registry
from synopse.communication.tools.base import ToolInputError
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


def test_control_task_schema_uses_canonical_command_values():
    registry = build_default_tool_registry(InMemoryBlackboard())

    command_type_schema = registry.get("control_task").input_schema["properties"]["command_type"]

    assert command_type_schema == {
        "type": "string",
        "enum": [command_type.value for command_type in TaskCommandType],
    }


def test_create_task_schema_uses_registered_executor_values():
    registry = build_default_tool_registry(
        InMemoryBlackboard(),
        executor_types=["mock", "codex"],
    )

    preferred_executor_schema = registry.get("create_task").input_schema["properties"][
        "preferred_executor"
    ]

    assert preferred_executor_schema == {
        "anyOf": [
            {"type": "string", "enum": ["codex", "mock"]},
            {"type": "null"},
        ]
    }


@pytest.mark.anyio
async def test_control_task_rejects_non_canonical_command_aliases():
    store = InMemoryBlackboard()
    registry = build_default_tool_registry(store)
    created = await registry.get("create_task")(
        title="Draft email",
        goal="Draft an email reply",
    )

    with pytest.raises(ToolInputError, match="Invalid control_task command_type 'resume'"):
        await registry.get("control_task")(
            task_id=created.task_id,
            command_type="resume",
        )

    commands = await store.list_commands(created.task_id)
    assert commands == []


@pytest.mark.anyio
async def test_create_task_rejects_unknown_executor_ids():
    store = InMemoryBlackboard()
    registry = build_default_tool_registry(store, executor_types=["mock"])

    with pytest.raises(ToolInputError, match="Invalid create_task preferred_executor 'User'"):
        await registry.get("create_task")(
            title="Draft email",
            goal="Draft an email reply",
            preferred_executor="User",
        )

    assert await store.list_tasks() == []
