import pytest

from synapse.blackboard import InMemoryBlackboard
from synapse.communication import CommunicationBrain
from synapse.communication.model import ToolCall
from synapse.communication.models import ScriptedCommunicationModel
from synapse.communication.models.scripted import ScriptedPlan
from synapse.protocol import Task, TaskSummary


@pytest.mark.anyio
async def test_query_summary_flow():
    store = InMemoryBlackboard()
    await store.put_task(Task(task_id="task_1", root_task_id="task_1", title="Draft email", goal="Draft email"))
    await store.put_summary(
        TaskSummary(
            task_id="task_1",
            conversational_summary="The draft is half done.",
            latest_user_visible_status="running",
        )
    )
    model = ScriptedCommunicationModel(
        {
            "How is the email going?": ScriptedPlan(
                conversational_act="inform_progress",
                tool_calls=[ToolCall(name="query_task_summary", args={"reference": "email"})],
            )
        }
    )
    brain = CommunicationBrain(store, model)

    result = await brain.handle_user_message("conv-1", "How is the email going?")

    assert result.reply_text == "The draft is half done."
