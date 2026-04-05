import pytest

from synopse.blackboard import InMemoryBlackboard
from synopse.communication.context import (
    DEFAULT_HISTORY_LIMIT,
    CommunicationContextBuilder,
)
from synopse.communication.history import InMemoryConversationHistory
from synopse.protocol import Task


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
    assert context.available_tools == ["create_task", "query_task_summary"]


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
