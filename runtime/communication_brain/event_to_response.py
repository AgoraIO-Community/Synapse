from __future__ import annotations

from runtime.infrastructure.ids import new_id
from runtime.protocols.conversation import (
    CommunicationEvent,
    ConversationAction,
    ConversationActionType,
)
from runtime.protocols.execution import ExecutionEvent, ExecutionEventType


class EventToResponseMapper:
    def _preferred_completion_text(self, event: ExecutionEvent) -> str | None:
        if event.progress_message and event.progress_message != "Task completed successfully.":
            return event.progress_message

        for artifact in event.artifacts_delta:
            inline_value = artifact.inline_value
            if isinstance(inline_value, str) and inline_value.strip():
                return inline_value.strip()

        return event.progress_message

    def on_execution_event(
        self, session_id: str, event: ExecutionEvent
    ) -> ConversationAction | None:
        mapping = {
            ExecutionEventType.PROGRESS: ConversationActionType.INFORM_PROGRESS,
            ExecutionEventType.BLOCKED: ConversationActionType.INFORM_BLOCKED,
            ExecutionEventType.COMPLETED: ConversationActionType.INFORM_DONE,
            ExecutionEventType.FAILED: ConversationActionType.INFORM_FAILED,
            ExecutionEventType.CANCELED: ConversationActionType.INFORM_CANCELED,
        }
        action_type = mapping.get(event.event_type)
        if action_type is None:
            return None

        reason = event.progress_message
        if event.event_type == ExecutionEventType.COMPLETED:
            reason = self._preferred_completion_text(event)

        return ConversationAction(
            action_id=new_id("conv"),
            action_type=action_type,
            target_task_id=event.task_id,
            reason=reason,
            metadata={
                "execution_event": event.model_dump(mode="json"),
                "executor_id": event.executor_id,
                "execution_event_type": event.event_type.value,
                "status": event.status.value,
                "progress_message": event.progress_message,
                "preferred_result_text": reason,
                "artifacts": [artifact.model_dump(mode="json") for artifact in event.artifacts_delta],
            },
        )

    def to_event(
        self, session_id: str, action: ConversationAction
    ) -> CommunicationEvent:
        return CommunicationEvent(
            event_id=new_id("comm_event"),
            session_id=session_id,
            action=action,
        )
