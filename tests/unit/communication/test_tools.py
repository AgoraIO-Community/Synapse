import pytest

from synapse.blackboard import InMemoryBlackboard
from synapse.communication.tools import build_default_tool_registry
from synapse.communication.tools.base import ToolInputError
from synapse.protocol import MutationType, TaskCommandType


@pytest.mark.anyio
async def test_create_update_note_constraint_control_and_query_tools():
    store = InMemoryBlackboard()
    registry = build_default_tool_registry(store)

    created = await registry.get("create_task")(
        title="Draft email",
        goal="Draft an email reply",
        mock_safe=True,
    )
    assert created.task_id.startswith("task-")
    assert created.preferred_executor == "mock"

    updated = await registry.get("update_task")(
        task_id=created.task_id,
        patch={"latest_instruction": "Make it shorter."},
    )
    assert updated.latest_instruction == "Make it shorter."

    noted = await registry.get("add_task_note")(
        task_id=created.task_id,
        note="Keep it friendly.",
    )
    assert noted.metadata["notes"] == ["Keep it friendly."]

    constrained = await registry.get("add_constraint")(
        task_id=created.task_id,
        constraint="Do not send yet.",
        category="delivery",
    )
    assert constrained.metadata["constraints"] == [
        {"constraint": "Do not send yet.", "category": "delivery"}
    ]

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
    assert [mutation.mutation_type for mutation in detail["mutations"]] == [
        MutationType.CREATE,
        MutationType.UPDATE,
        MutationType.ADD_TASK_NOTE,
        MutationType.ADD_CONSTRAINT,
    ]


@pytest.mark.anyio
async def test_list_tasks_returns_ranked_matches():
    store = InMemoryBlackboard()
    registry = build_default_tool_registry(store)
    await registry.get("create_task")(
        title="Draft sales email",
        goal="Draft sales email",
        mock_safe=True,
    )
    await registry.get("create_task")(
        title="Book flight",
        goal="Book flight to Shanghai",
        mock_safe=True,
    )

    result = await registry.get("list_tasks")(reference="email")

    assert result["reference"] == "email"
    assert len(result["matches"]) == 1
    assert result["matches"][0]["title"] == "Draft sales email"


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
        default_executor_type="codex",
    )

    preferred_executor_schema = registry.get("create_task").input_schema["properties"][
        "preferred_executor"
    ]
    mock_safe_schema = registry.get("create_task").input_schema["properties"]["mock_safe"]

    assert preferred_executor_schema == {
        "anyOf": [
            {"type": "string", "enum": ["codex", "mock"]},
            {"type": "null"},
        ]
    }
    assert mock_safe_schema == {"type": "boolean"}


@pytest.mark.anyio
async def test_control_task_rejects_non_canonical_command_aliases():
    store = InMemoryBlackboard()
    registry = build_default_tool_registry(store)
    created = await registry.get("create_task")(
        title="Draft email",
        goal="Draft an email reply",
        mock_safe=True,
    )

    with pytest.raises(ToolInputError, match="Invalid control_task command_type 'resume'"):
        await registry.get("control_task")(
            task_id=created.task_id,
            command_type="resume",
        )

    commands = await store.list_commands(created.task_id)
    assert commands == []


@pytest.mark.anyio
async def test_update_task_rejects_unknown_patch_fields():
    store = InMemoryBlackboard()
    registry = build_default_tool_registry(store)
    created = await registry.get("create_task")(
        title="Draft email",
        goal="Draft an email reply",
        mock_safe=True,
    )

    with pytest.raises(ToolInputError, match="Invalid update_task fields"):
        await registry.get("update_task")(
            task_id=created.task_id,
            patch={"note": "Keep it shorter."},
        )


@pytest.mark.anyio
async def test_query_tools_reject_ambiguous_reference():
    store = InMemoryBlackboard()
    registry = build_default_tool_registry(store)
    await registry.get("create_task")(
        title="Draft email",
        goal="Draft an email reply",
        mock_safe=True,
    )
    await registry.get("create_task")(
        title="Send email",
        goal="Send an email follow-up",
        mock_safe=True,
    )

    with pytest.raises(ToolInputError, match="ambiguous"):
        await registry.get("query_task_summary")(reference="email")


@pytest.mark.anyio
async def test_create_task_rejects_unknown_executor_ids():
    store = InMemoryBlackboard()
    registry = build_default_tool_registry(
        store,
        executor_types=["mock"],
        default_executor_type="mock",
    )

    with pytest.raises(ToolInputError, match="Invalid create_task preferred_executor 'User'"):
        await registry.get("create_task")(
            title="Draft email",
            goal="Draft an email reply",
            preferred_executor="User",
        )

    assert await store.list_tasks() == []


@pytest.mark.anyio
async def test_create_task_uses_default_executor_when_omitted():
    store = InMemoryBlackboard()
    registry = build_default_tool_registry(
        store,
        executor_types=["mock", "codex"],
        default_executor_type="codex",
    )

    created = await registry.get("create_task")(
        title="Draft email",
        goal="Draft an email reply",
    )

    assert created.preferred_executor == "codex"


@pytest.mark.anyio
async def test_create_task_rejects_mock_default_without_explicit_mock_safe():
    store = InMemoryBlackboard()
    registry = build_default_tool_registry(
        store,
        executor_types=["mock"],
        default_executor_type="mock",
    )

    with pytest.raises(ToolInputError, match="real executor is required"):
        await registry.get("create_task")(
            title="Draft email",
            goal="Draft an email reply",
        )
