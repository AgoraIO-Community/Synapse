from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from synopse.blackboard import BlackboardStore
from synopse.blackboard.store import BlackboardWriteEvent, BlackboardWriteKind
from synopse.communication import CommunicationBrain
from synopse.communication.types import CommunicationTurnResult
from synopse.observability.emitters import NotificationDiagnosticEmitter
from synopse.observability.reason_codes import (
    NOTIFICATION_DEFERRED_ASSISTANT_BUSY,
    NOTIFICATION_DEFERRED_PENDING_USER_MESSAGE,
)
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
        observability: NotificationDiagnosticEmitter | None = None,
    ) -> None:
        self._store = store
        self._communication_brain = communication_brain
        self._conversation_id = conversation_id
        self._candidate_builder = candidate_builder or NotificationCandidateBuilder()
        self._policy = policy or NotificationPolicy()
        self._observability = observability
        self._conversation_event_callback: Callable[..., Awaitable[None] | None] | None = None

    def set_conversation_event_callback(
        self,
        callback: Callable[..., Awaitable[None] | None] | None,
    ) -> None:
        self._conversation_event_callback = callback

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
            if self._observability is not None:
                self._observability.candidate_created(candidate=candidate)
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
            if self._observability is not None:
                self._observability.candidate_created(candidate=candidate)
            return True

        return False

    async def process_pending(
        self,
        *,
        assistant_busy: bool,
        has_pending_user_messages: bool,
    ) -> NotificationProcessingResult:
        candidates = await self._store.list_notification_candidates()
        pending_candidates = [
            candidate
            for candidate in candidates
            if candidate.delivery_status == NotificationDeliveryStatus.PENDING
        ]
        plan = self._policy.plan(
            candidates,
            assistant_busy=assistant_busy,
            has_pending_user_messages=has_pending_user_messages,
        )
        if self._observability is not None and pending_candidates:
            self._observability.plan_adopted(
                policy_name=self._policy.__class__.__name__,
                merge_window_seconds=self._policy.merge_window_seconds,
                pending_candidates=pending_candidates,
                plan=plan,
                assistant_busy=assistant_busy,
                has_pending_user_messages=has_pending_user_messages,
            )
        if not plan.groups:
            pending_count = len(pending_candidates)
            if self._observability is not None and pending_count > 0:
                if assistant_busy:
                    self._observability.delivery_deferred(
                        reason_code=NOTIFICATION_DEFERRED_ASSISTANT_BUSY,
                        pending_count=pending_count,
                    )
                elif has_pending_user_messages:
                    self._observability.delivery_deferred(
                        reason_code=NOTIFICATION_DEFERRED_PENDING_USER_MESSAGE,
                        pending_count=pending_count,
                    )
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
        if self._observability is not None:
            self._observability.batch_emitted(
                candidates=candidates,
                key_task_id=result.notification_key_task_id,
                relevant_task_ids=result.notification_relevant_task_ids,
            )
        if self._conversation_event_callback is not None:
            maybe_awaitable = self._conversation_event_callback(
                message_id=result.message_id,
                text=result.reply_text,
                source="notification",
            )
            if maybe_awaitable is not None:
                await maybe_awaitable
        return result
