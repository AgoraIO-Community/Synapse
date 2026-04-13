import pytest

from synapse.blackboard import InMemoryBlackboard
from synapse.communication import CommunicationBrain
from synapse.communication.model import CommunicationModelResult, ToolCall
from synapse.communication.models import ScriptedCommunicationModel
from synapse.communication.models.scripted import ScriptedPlan


@pytest.mark.anyio
async def test_communication_brain_creates_task_and_returns_natural_reply():
    store = InMemoryBlackboard()
    model = ScriptedCommunicationModel(
        {
            "Help me draft an email": ScriptedPlan(
                conversational_act="acknowledge_and_start",
                tool_calls=[
                    ToolCall(
                        name="create_task",
                        args={"title": "Draft email", "goal": "Draft an email", "mock_safe": True},
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


class CapturingModel:
    def __init__(self) -> None:
        self.seen_histories: list[list[str]] = []

    async def respond(self, *, user_text, context, tool_registry):
        self.seen_histories.append([entry.text for entry in context.recent_history])
        return CommunicationModelResult(
            reply_text=f"reply to {user_text}",
            conversational_act="model_reply",
        )


@pytest.mark.anyio
async def test_communication_brain_replays_local_history_across_turns():
    store = InMemoryBlackboard()
    model = CapturingModel()
    brain = CommunicationBrain(store, model)

    await brain.handle_user_message("conv-1", "first")
    await brain.handle_user_message("conv-1", "second")

    assert model.seen_histories == [
        ["first"],
        ["first", "reply to first", "second"],
    ]
