import pytest

from newbro.blackboard import InMemoryBlackboard
from newbro.communication import CommunicationBrain
from newbro.communication.model import ToolCall
from newbro.communication.models import ScriptedCommunicationModel
from newbro.communication.models.scripted import ScriptedPlan


@pytest.mark.anyio
async def test_create_task_flow():
    store = InMemoryBlackboard()
    model = ScriptedCommunicationModel(
        {
            "Check Tokyo flights": ScriptedPlan(
                conversational_act="acknowledge_and_start",
                tool_calls=[
                    ToolCall(
                        name="create_task",
                        args={
                            "title": "Check Tokyo flights",
                            "goal": "Check Tokyo flights",
                            "mock_safe": True,
                        },
                    )
                ],
            )
        }
    )
    brain = CommunicationBrain(store, model)

    result = await brain.handle_user_message("conv-1", "Check Tokyo flights")

    assert result.affected_task_ids
    assert "successfully" not in result.reply_text.lower()
