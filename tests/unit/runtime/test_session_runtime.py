import pytest

from synopse.communication.model import CommunicationDecision
from synopse.communication.models import ScriptedCommunicationModel
from synopse.runtime.session import create_session_runtime


@pytest.mark.anyio
async def test_session_runtime_publish_snapshot_notifies_subscribers():
    session = create_session_runtime(
        "session-1",
        model=ScriptedCommunicationModel(
            {"__default__": CommunicationDecision(conversational_act="request_clarification")}
        ),
    )
    queue = session.subscribe()

    snapshot = await session.publish_snapshot()
    published = await queue.get()

    assert snapshot.session_id == "session-1"
    assert published.session_id == "session-1"

    session.unsubscribe(queue)
