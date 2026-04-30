import pytest

from newbro.blackboard import InMemoryBlackboard
from newbro.communication import CommunicationBrain
from newbro.communication.model import ToolCall
from newbro.communication.models import ScriptedCommunicationModel
from newbro.communication.models.scripted import ScriptedPlan
from newbro.protocol import Task, TaskSummary


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
