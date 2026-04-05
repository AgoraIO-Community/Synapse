import pytest

from synopse.blackboard import InMemoryBlackboard
from synopse.communication.context import CommunicationContextBuilder
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

    context = await builder.build("conv-1", available_tools=["create_task", "query_task_summary"])
    assert len(context.recent_history) == 1
    assert len(context.tasks) == 1
    assert context.available_tools == ["create_task", "query_task_summary"]
