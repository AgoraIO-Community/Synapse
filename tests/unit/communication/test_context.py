import pytest

from synapse.blackboard import InMemoryBlackboard
from synapse.communication.context import (
    DEFAULT_HISTORY_LIMIT,
    CommunicationContextBuilder,
)
from synapse.communication.history import InMemoryConversationHistory
from synapse.executor_core import ExecutorCapabilities
from synapse.protocol import Task, TaskExecutionDetailEntry


@pytest.mark.anyio
async def test_context_builder_collects_history_tasks_and_tools():
    store = InMemoryBlackboard()
    history = InMemoryConversationHistory()
    history.append_user("conv-1", "Help me")
    await store.put_task(
        Task(task_id="task_1", root_task_id="task_1", title="A", goal="A")
    )
    builder = CommunicationContextBuilder(store, history)

    context = await builder.build(
        "conv-1",
        available_tools=["create_task", "query_task_summary"],
    )
    assert len(context.recent_history) == 1
    assert len(context.tasks) == 1
    assert len(context.active_tasks) == 1
    assert len(context.recent_tasks) == 1
    assert context.task_execution_details == {}
    assert context.executor_runtime.has_real_executor is False
    assert context.executor_runtime.available_executor_types == []
    assert context.available_tools == ["create_task", "query_task_summary"]


@pytest.mark.anyio
async def test_context_builder_includes_executor_runtime_summary():
    store = InMemoryBlackboard()
    history = InMemoryConversationHistory()
    builder = CommunicationContextBuilder(
        store,
        history,
        executor_capabilities=[
            ExecutorCapabilities(executor_type="mock"),
            ExecutorCapabilities(executor_type="codex", supports_follow_up=True),
        ],
        default_executor_type="codex",
    )

    context = await builder.build("conv-1", available_tools=["create_task"])

    assert context.executor_runtime.has_real_executor is True
    assert context.executor_runtime.available_executor_types == ["mock", "codex"]
    assert context.executor_runtime.default_executor_type == "codex"


@pytest.mark.anyio
async def test_context_builder_uses_bounded_history_window():
    store = InMemoryBlackboard()
    history = InMemoryConversationHistory()
    for index in range(DEFAULT_HISTORY_LIMIT + 5):
        history.append_user("conv-1", f"msg-{index}")
    builder = CommunicationContextBuilder(store, history)

    context = await builder.build(
        "conv-1",
        available_tools=["create_task"],
    )

    assert len(context.recent_history) == DEFAULT_HISTORY_LIMIT
    assert context.recent_history[0].text == "msg-5"
    assert context.recent_history[-1].text == f"msg-{DEFAULT_HISTORY_LIMIT + 4}"


@pytest.mark.anyio
async def test_context_builder_includes_recent_execution_detail_windows():
    store = InMemoryBlackboard()
    history = InMemoryConversationHistory()
    await store.put_task(Task(task_id="task_1", root_task_id="task_1", title="A", goal="A"))
    await store.put_task(Task(task_id="task_2", root_task_id="task_2", title="B", goal="B"))
    await store.append_task_execution_detail(
        TaskExecutionDetailEntry(
            detail_id="detail-1",
            task_id="task_1",
            run_id="run-1",
            execution_session_id="session-1",
            event_type="progress",
            text="first",
            created_at="2026-04-21T00:00:01+00:00",
        )
    )
    await store.append_task_execution_detail(
        TaskExecutionDetailEntry(
            detail_id="detail-2",
            task_id="task_2",
            run_id="run-2",
            execution_session_id="session-2",
            event_type="progress",
            text="second",
            created_at="2026-04-21T00:00:02+00:00",
        )
    )
    builder = CommunicationContextBuilder(store, history)

    context = await builder.build("conv-1", available_tools=["query_task_detail"])

    assert list(context.task_execution_details.keys()) == ["task_2", "task_1"]
    assert context.task_execution_details["task_2"][0].text == "second"
