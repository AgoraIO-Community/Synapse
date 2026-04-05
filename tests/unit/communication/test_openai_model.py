import pytest

from synopse.communication.context import CommunicationContext
from synopse.communication.history import ConversationEntry
from synopse.communication.models.openai import OpenAICommunicationModel
from synopse.protocol import Task, TaskStatus


class FakeProvider:
    def __init__(self, payload):
        self.payload = payload

    async def parse_structured(self, **kwargs):
        return self.payload


class FakePayload:
    conversational_act = "acknowledge_and_start"
    tool_calls = []
    reply_override = "I'll take care of that."


@pytest.mark.anyio
async def test_openai_model_maps_payload_to_communication_decision():
    model = OpenAICommunicationModel(FakeProvider(FakePayload()))
    context = CommunicationContext(
        conversation_id="conv-1",
        recent_history=[ConversationEntry(role="user", text="hi")],
        tasks=[
            Task(
                task_id="task_1",
                root_task_id="task_1",
                title="Draft email",
                goal="Draft email",
                status=TaskStatus.CREATED,
            )
        ],
        summaries={},
        available_tools=["create_task"],
    )

    decision = await model.decide(user_text="Draft email", context=context)

    assert decision.conversational_act == "acknowledge_and_start"
    assert decision.reply_override == "I'll take care of that."
