import pytest

from synapse.blackboard import InMemoryBlackboard
from synapse.communication import CommunicationBrain
from synapse.communication.model import ToolCall
from synapse.communication.models import ScriptedCommunicationModel
from synapse.communication.models.scripted import ScriptedPlan


@pytest.mark.anyio
async def test_update_task_flow():
    store = InMemoryBlackboard()
    model = ScriptedCommunicationModel(
        {
            "Make it shorter": ScriptedPlan(
                conversational_act="acknowledge_and_modify",
                tool_calls=[
                    ToolCall(
                        name="add_task_note",
                        args={"reference": "email", "note": "Make it shorter."},
                    )
                ],
            )
        }
    )
    from synapse.protocol import Task

    await store.put_task(Task(task_id="task_1", root_task_id="task_1", title="Draft email", goal="Draft email"))
    brain = CommunicationBrain(store, model)

    result = await brain.handle_user_message("conv-1", "Make it shorter")

    task = await store.get_task("task_1")
    assert task is not None
    assert task.metadata["notes"] == ["Make it shorter."]
    assert result.conversational_act == "acknowledge_and_modify"
