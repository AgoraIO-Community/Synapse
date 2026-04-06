from __future__ import annotations

from dataclasses import dataclass

from synopse.protocol import NotificationCandidate

from ..logger import DiagnosticLogger


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

    def batch_emitted(self, *, candidates: list[NotificationCandidate]) -> None:
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
            },
        )
