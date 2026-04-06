from __future__ import annotations

from dataclasses import dataclass

from synopse.blackboard import BlackboardStore
from synopse.blackboard.store import BlackboardWriteEvent, BlackboardWriteKind
from synopse.communication import CommunicationBrain
from synopse.communication.types import CommunicationTurnResult
from synopse.protocol import NotificationCandidate, NotificationDeliveryStatus

from .candidate_builder import NotificationCandidateBuilder
from .policy import NotificationPolicy


@dataclass(slots=True)
class NotificationProcessingResult:
    emitted_messages: list[CommunicationTurnResult]
    next_due_seconds: float | None = None


class NotificationManager:
    def __init__(
        self,
        store: BlackboardStore,
        communication_brain: CommunicationBrain,
        *,
        conversation_id: str,
        candidate_builder: NotificationCandidateBuilder | None = None,
        policy: NotificationPolicy | None = None,
    ) -> None:
        self._store = store
        self._communication_brain = communication_brain
        self._conversation_id = conversation_id
        self._candidate_builder = candidate_builder or NotificationCandidateBuilder()
        self._policy = policy or NotificationPolicy()

    async def handle_blackboard_write(self, event: BlackboardWriteEvent) -> bool:
        candidates = await self._store.list_notification_candidates()

        if event.kind == BlackboardWriteKind.RUN and event.entity_id:
            run = await self._store.get_run(event.entity_id)
            if run is None or run.status.value not in {"completed", "blocked"}:
                return False
            task = await self._store.get_task(run.task_id)
            if task is None:
                return False
            summary = await self._store.get_summary(task.task_id)
            candidate = self._candidate_builder.build_from_run(
                task=task,
                run=run,
                summary=summary,
                existing=candidates,
            )
            if candidate is None:
                return False
            await self._store.put_notification_candidate(candidate)
            return True

        if event.kind == BlackboardWriteKind.SUMMARY and event.entity_id:
            summary = await self._store.get_summary(event.entity_id)
            task = await self._store.get_task(event.entity_id)
            if task is None:
                return False
            candidate = self._candidate_builder.build_from_summary(
                task=task,
                summary=summary,
                existing=candidates,
            )
            if candidate is None:
                return False
            await self._store.put_notification_candidate(candidate)
            return True

        return False

    async def process_pending(
        self,
        *,
        assistant_busy: bool,
        has_pending_user_messages: bool,
    ) -> NotificationProcessingResult:
        candidates = await self._store.list_notification_candidates()
        plan = self._policy.plan(
            candidates,
            assistant_busy=assistant_busy,
            has_pending_user_messages=has_pending_user_messages,
        )
        if not plan.groups:
            return NotificationProcessingResult(
                emitted_messages=[],
                next_due_seconds=plan.next_due_seconds,
            )

        emitted: list[CommunicationTurnResult] = []
        for group in plan.groups:
            message = await self._emit_group(group.candidates)
            emitted.append(message)

        return NotificationProcessingResult(
            emitted_messages=emitted,
            next_due_seconds=plan.next_due_seconds,
        )

    async def _emit_group(
        self,
        candidates: list[NotificationCandidate],
    ) -> CommunicationTurnResult:
        result = await self._communication_brain.emit_notification(
            self._conversation_id,
            candidates=candidates,
        )
        for candidate in candidates:
            await self._store.put_notification_candidate(
                candidate.model_copy(
                    update={
                        "delivery_status": NotificationDeliveryStatus.EMITTED,
                    }
                )
            )
        return result
