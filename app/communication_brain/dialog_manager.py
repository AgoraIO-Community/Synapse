from __future__ import annotations

from app.infrastructure.ids import new_id
from app.protocols.conversation import (
    CommunicationEvent,
    ConversationAction,
    ConversationActionType,
)
from app.protocols.execution import ExecutionEvent, ExecutionEventType


class DialogManager:
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

        return ConversationAction(
            action_id=new_id("conv"),
            action_type=action_type,
            target_task_id=event.task_id,
            reason=event.progress_message,
        )

    def to_event(
        self, session_id: str, action: ConversationAction
    ) -> CommunicationEvent:
        return CommunicationEvent(
            event_id=new_id("comm_event"),
            session_id=session_id,
            action=action,
        )
