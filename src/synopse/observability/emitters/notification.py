from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from synopse.protocol import NotificationCandidate

from ..logger import DiagnosticLogger

if TYPE_CHECKING:
    from synopse.notification.policy import NotificationDeliveryPlan


@dataclass(slots=True)
class NotificationDiagnosticEmitter:
    logger: DiagnosticLogger

    def candidate_created(self, *, candidate: NotificationCandidate) -> None:
        self.logger.emit_event(
            level="INFO",
            event_name="notify.candidate.created",
            component="notification.manager",
            summary="Notification candidate created",
            task_id=candidate.task_id,
            run_id=candidate.source_run_id,
            notification_id=candidate.candidate_id,
            outcome=candidate.candidate_type.value,
            details={
                "delivery_status": candidate.delivery_status.value,
                "requires_immediate_delivery": candidate.requires_immediate_delivery,
            },
        )

    def delivery_deferred(
        self,
        *,
        reason_code: str,
        pending_count: int,
    ) -> None:
        self.logger.emit_event(
            level="WARNING",
            event_name="notify.delivery.deferred",
            component="notification.policy",
            summary="Notification delivery deferred",
            reason_code=reason_code,
            details={"pending_count": pending_count},
        )

    def plan_adopted(
        self,
        *,
        policy_name: str,
        merge_window_seconds: float,
        pending_candidates: list[NotificationCandidate],
        plan: NotificationDeliveryPlan,
        assistant_busy: bool,
        has_pending_user_messages: bool,
    ) -> None:
        self.logger.emit_event(
            level="INFO",
            event_name="notify.plan.adopted",
            component="notification.policy",
            summary="Notification delivery plan adopted",
            task_id=pending_candidates[0].task_id if pending_candidates else None,
            notification_id=pending_candidates[0].candidate_id if len(pending_candidates) == 1 else None,
            details={
                "policy_name": policy_name,
                "merge_window_seconds": merge_window_seconds,
                "assistant_busy": assistant_busy,
                "has_pending_user_messages": has_pending_user_messages,
                "pending_candidate_ids": [candidate.candidate_id for candidate in pending_candidates],
                "pending_task_ids": sorted({candidate.task_id for candidate in pending_candidates}),
                "group_count": len(plan.groups),
                "groups": [
                    {
                        "candidate_ids": [candidate.candidate_id for candidate in group.candidates],
                        "task_ids": sorted({candidate.task_id for candidate in group.candidates}),
                        "merge_key": group.candidates[0].merge_key if group.candidates else None,
                        "requires_immediate_delivery": any(
                            candidate.requires_immediate_delivery for candidate in group.candidates
                        ),
                    }
                    for group in plan.groups
                ],
                "next_due_seconds": plan.next_due_seconds,
            },
        )

    def batch_emitted(
        self,
        *,
        candidates: list[NotificationCandidate],
        key_task_id: str | None,
        relevant_task_ids: list[str],
    ) -> None:
        self.logger.emit_event(
            level="INFO",
            event_name="notify.batch.emitted",
            component="notification.manager",
            summary="Notification batch emitted",
            task_id=candidates[0].task_id if candidates else None,
            run_id=candidates[0].source_run_id if candidates else None,
            notification_id=candidates[0].candidate_id if len(candidates) == 1 else None,
            details={
                "candidate_ids": [candidate.candidate_id for candidate in candidates],
                "task_ids": sorted({candidate.task_id for candidate in candidates}),
                "count": len(candidates),
                "key_task_id": key_task_id,
                "relevant_task_ids": relevant_task_ids,
            },
        )
