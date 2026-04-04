import asyncio

from runtime.protocols.stream import StreamCategory
from runtime.shared_blackboard.runtime_state import RuntimeStateStore


def test_runtime_state_store_can_publish_transient_events_without_persisting_them():
    store = RuntimeStateStore()
    session = store.create_session()
    queue = store.subscribe(session.session_id)

    async def main():
        return await store.publish_transient(
            session.session_id,
            StreamCategory.COMMUNICATION,
            "response_chunk",
            "communication_brain",
            {"render_text": "Hello"},
        )

    event = asyncio.run(main())
    queued = queue.get_nowait()

    assert event.event_type == "response_chunk"
    assert queued.stream_event_id == event.stream_event_id
    assert store.get_session(session.session_id).event_log == []
    assert store.snapshot(session.session_id).last_sequence == 1
