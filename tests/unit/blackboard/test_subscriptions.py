from __future__ import annotations

import pytest

from newbro.blackboard.store import BlackboardWriteEvent, BlackboardWriteKind
from newbro.blackboard.subscriptions import SubscriptionManager


@pytest.mark.anyio
async def test_subscription_manager_publish_and_unsubscribe():
    subscriptions = SubscriptionManager()
    queue = subscriptions.subscribe()

    await subscriptions.publish(
        BlackboardWriteEvent(
            kind=BlackboardWriteKind.TASK,
            entity_id="task_1",
            task_id="task_1",
        )
    )
    event = await queue.get()
    assert event.entity_id == "task_1"

    subscriptions.unsubscribe(queue)
