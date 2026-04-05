import pytest

from synopse.blackboard import InMemoryBlackboard
from synopse.communication import CommunicationBrain
from synopse.communication.model import ToolCall
from synopse.communication.models import ScriptedCommunicationModel
from synopse.communication.models.scripted import ScriptedPlan
from synopse.protocol import Task, TaskCommandType


@pytest.mark.anyio
async def test_control_task_flow():
    store = InMemoryBlackboard()
    await store.put_task(Task(task_id="task_1", root_task_id="task_1", title="Draft email", goal="Draft email"))
    model = ScriptedCommunicationModel(
        {
            "Hold that email": ScriptedPlan(
                conversational_act="acknowledge_and_hold",
                tool_calls=[
                    ToolCall(
                        name="control_task",
                        args={"reference": "email", "command_type": TaskCommandType.PAUSE_TASK.value},
                    )
                ],
            )
        }
    )
    brain = CommunicationBrain(store, model)

    result = await brain.handle_user_message("conv-1", "Hold that email")

    commands = await store.list_commands("task_1")
    assert commands[-1].command_type == TaskCommandType.PAUSE_TASK
    assert result.conversational_act == "acknowledge_and_hold"
