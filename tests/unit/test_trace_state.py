import asyncio

from runtime.protocols.trace import TraceStage
from runtime.shared_blackboard.trace_state import TraceStateStore


def test_trace_state_store_publishes_ordered_events():
    store = TraceStateStore()
    session_id = "session_test"

    async def main():
        first = await store.publish(
            session_id,
            TraceStage.API,
            "message_received",
            "api.messages",
            {"text": "hello"},
        )
        second = await store.publish(
            session_id,
            TraceStage.ACTION_ROUTER,
            "routing_completed",
            "action_router",
            {"action_count": 1},
        )
        return first, second

    first, second = asyncio.run(main())

    assert first.trace_sequence == 1
    assert second.trace_sequence == 2
    snapshot = store.snapshot(session_id)
    assert snapshot.last_trace_sequence == 2
    assert len(snapshot.recent_traces) == 2
