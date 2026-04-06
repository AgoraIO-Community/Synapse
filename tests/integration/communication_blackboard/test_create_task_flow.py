import pytest

from synopse.blackboard import InMemoryBlackboard
from synopse.communication import CommunicationBrain
from synopse.communication.model import ToolCall
from synopse.communication.models import ScriptedCommunicationModel
from synopse.communication.models.scripted import ScriptedPlan


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
