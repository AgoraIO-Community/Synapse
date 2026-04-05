import pytest

from synopse.blackboard import InMemoryBlackboard
from synopse.communication import CommunicationBrain
from synopse.communication.model import ToolCall
from synopse.communication.models import ScriptedCommunicationModel
from synopse.communication.models.scripted import ScriptedPlan


@pytest.mark.anyio
async def test_update_task_flow():
    store = InMemoryBlackboard()
    model = ScriptedCommunicationModel(
        {
            "Make it shorter": ScriptedPlan(
                conversational_act="acknowledge_and_modify",
                tool_calls=[
                    ToolCall(
                        name="update_task",
                        args={"reference": "email", "patch": {"latest_instruction": "Shorter"}},
                    )
                ],
            )
        }
    )
    from synopse.protocol import Task

    await store.put_task(Task(task_id="task_1", root_task_id="task_1", title="Draft email", goal="Draft email"))
    brain = CommunicationBrain(store, model)

    result = await brain.handle_user_message("conv-1", "Make it shorter")

    task = await store.get_task("task_1")
    assert task is not None
    assert task.latest_instruction == "Shorter"
    assert result.conversational_act == "acknowledge_and_modify"
