from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Callable

from synopse.protocol import NotificationCandidate, NotificationDeliveryStatus


@dataclass(slots=True)
class NotificationDeliveryGroup:
    candidates: list[NotificationCandidate] = field(default_factory=list)


@dataclass(slots=True)
class NotificationDeliveryPlan:
    groups: list[NotificationDeliveryGroup] = field(default_factory=list)
    next_due_seconds: float | None = None


class NotificationPolicy:
    def __init__(
        self,
        *,
        merge_window_seconds: float = 2.0,
        now_fn: Callable[[], datetime] | None = None,
    ) -> None:
        self._merge_window_seconds = merge_window_seconds
        self._now_fn = now_fn or (lambda: datetime.now(UTC))

    def plan(
        self,
        candidates: list[NotificationCandidate],
        *,
        assistant_busy: bool,
        has_pending_user_messages: bool,
    ) -> NotificationDeliveryPlan:
        pending = [
            candidate
            for candidate in candidates
            if candidate.delivery_status == NotificationDeliveryStatus.PENDING
        ]
        if not pending:
            return NotificationDeliveryPlan()
        if assistant_busy or has_pending_user_messages:
            return NotificationDeliveryPlan()

        now = self._now_fn()
        groups: list[NotificationDeliveryGroup] = []

        for candidate in pending:
            if candidate.requires_immediate_delivery:
                groups.append(NotificationDeliveryGroup(candidates=[candidate]))

        completed_pending = [
            candidate
            for candidate in pending
            if not candidate.requires_immediate_delivery
        ]

        due_candidates: list[NotificationCandidate] = []
        next_due_seconds: float | None = None
        for candidate in completed_pending:
            due_at = self._due_at(candidate)
            if due_at <= now:
                due_candidates.append(candidate)
            else:
                seconds = max(0.0, (due_at - now).total_seconds())
                next_due_seconds = (
                    seconds
                    if next_due_seconds is None
                    else min(next_due_seconds, seconds)
                )

        if due_candidates:
            grouped: dict[str, list[NotificationCandidate]] = {}
            for candidate in due_candidates:
                grouped.setdefault(candidate.merge_key, []).append(candidate)
            for merge_key in sorted(grouped):
                grouped[merge_key].sort(key=lambda item: item.created_at)
                groups.append(NotificationDeliveryGroup(candidates=grouped[merge_key]))

        return NotificationDeliveryPlan(groups=groups, next_due_seconds=next_due_seconds)

    def _due_at(self, candidate: NotificationCandidate) -> datetime:
        created_at = datetime.fromisoformat(candidate.created_at)
        return created_at + timedelta(seconds=self._merge_window_seconds)
