import pytest

from synopse.blackboard import InMemoryBlackboard
from synopse.communication import CommunicationBrain
from synopse.communication.models import ScriptedCommunicationModel
from synopse.communication.model import CommunicationDecision, ToolCall


@pytest.mark.anyio
async def test_communication_brain_creates_task_and_returns_natural_reply():
    store = InMemoryBlackboard()
    model = ScriptedCommunicationModel(
        {
            "Help me draft an email": CommunicationDecision(
                conversational_act="acknowledge_and_start",
                tool_calls=[
                    ToolCall(
                        name="create_task",
                        args={"title": "Draft email", "goal": "Draft an email"},
                    )
                ],
            )
        }
    )
    brain = CommunicationBrain(store, model)

    result = await brain.handle_user_message("conv-1", "Help me draft an email")

    assert result.conversational_act == "acknowledge_and_start"
    assert "successfully" not in result.reply_text.lower()
    assert len(await store.list_tasks()) == 1
