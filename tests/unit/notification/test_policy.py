from datetime import UTC, datetime

from synapse.notification import NotificationPolicy
from synapse.protocol import (
    NotificationCandidate,
    NotificationCandidateType,
    NotificationDeliveryStatus,
    NotificationPriority,
)


def _candidate(
    *,
    candidate_id: str,
    candidate_type: NotificationCandidateType,
    created_at: str,
    immediate: bool,
    merge_key: str,
) -> NotificationCandidate:
    return NotificationCandidate(
        candidate_id=candidate_id,
        task_id="task-1",
        candidate_type=candidate_type,
        priority=NotificationPriority.P0 if immediate else NotificationPriority.P2,
        summary_short="update",
        created_at=created_at,
        delivery_status=NotificationDeliveryStatus.PENDING,
        merge_key=merge_key,
        requires_immediate_delivery=immediate,
    )


def test_policy_delivers_immediate_candidates_when_not_busy():
    policy = NotificationPolicy(
        now_fn=lambda: datetime(2026, 4, 6, 12, 0, 0, tzinfo=UTC)
    )
    candidate = _candidate(
        candidate_id="notif-1",
        candidate_type=NotificationCandidateType.BLOCKED,
        created_at="2026-04-06T11:59:59+00:00",
        immediate=True,
        merge_key="blocked:task-1",
    )

    plan = policy.plan([candidate], assistant_busy=False, has_pending_user_messages=False)

    assert len(plan.groups) == 1
    assert plan.groups[0].candidates[0].candidate_id == "notif-1"


def test_policy_merges_completed_candidates_after_window():
    policy = NotificationPolicy(
        now_fn=lambda: datetime(2026, 4, 6, 12, 0, 3, tzinfo=UTC)
    )
    candidates = [
        _candidate(
            candidate_id="notif-1",
            candidate_type=NotificationCandidateType.COMPLETED,
            created_at="2026-04-06T12:00:00+00:00",
            immediate=False,
            merge_key="completed_digest",
        ),
        _candidate(
            candidate_id="notif-2",
            candidate_type=NotificationCandidateType.COMPLETED,
            created_at="2026-04-06T12:00:01+00:00",
            immediate=False,
            merge_key="completed_digest",
        ),
    ]

    plan = policy.plan(candidates, assistant_busy=False, has_pending_user_messages=False)

    assert len(plan.groups) == 1
    assert len(plan.groups[0].candidates) == 2


def test_policy_defers_when_assistant_is_busy():
    policy = NotificationPolicy(
        now_fn=lambda: datetime(2026, 4, 6, 12, 0, 3, tzinfo=UTC)
    )
    candidate = _candidate(
        candidate_id="notif-1",
        candidate_type=NotificationCandidateType.COMPLETED,
        created_at="2026-04-06T12:00:00+00:00",
        immediate=False,
        merge_key="completed_digest",
    )

    plan = policy.plan([candidate], assistant_busy=True, has_pending_user_messages=False)

    assert plan.groups == []
