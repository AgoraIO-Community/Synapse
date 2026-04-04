from __future__ import annotations

from runtime.infrastructure.ids import new_id
from runtime.protocols.conversation import ConversationAction, ConversationActionType, Urgency
from runtime.protocols.runtime import ActionBundle, ConversationMode, RoutingDecision


class InteractionPolicy:
    def _build_action_metadata(
        self,
        decision: RoutingDecision,
        bundle: ActionBundle,
        *,
        user_message_text: str,
    ) -> dict:
        planned_actions = [
            {
                "action_type": action.action_type.value,
                "target_scope": action.target_scope.value,
                "payload": action.payload,
            }
            for action in bundle.actions
        ]
        return {
            "user_message": user_message_text,
            "conversation_mode": decision.conversation_mode.value,
            "priority_hint": decision.priority_hint.value,
            "needs_clarification": decision.needs_clarification,
            "planned_actions": planned_actions,
        }

    def build_initial_action(
        self,
        decision: RoutingDecision,
        bundle: ActionBundle,
        *,
        user_message_text: str,
    ) -> ConversationAction:
        metadata = self._build_action_metadata(
            decision,
            bundle,
            user_message_text=user_message_text,
        )
        if decision.conversation_mode == ConversationMode.CLARIFICATION or decision.needs_clarification:
            return ConversationAction(
                action_id=new_id("conv"),
                action_type=ConversationActionType.CLARIFY,
                urgency=Urgency.HIGH,
                reason=decision.clarification_reason,
                metadata=metadata,
            )

        if decision.conversation_mode == ConversationMode.CONVERSATION_ONLY:
            return ConversationAction(
                action_id=new_id("conv"),
                action_type=ConversationActionType.CHAT_REPLY,
                urgency=Urgency.NORMAL,
                metadata=metadata,
            )

        target_task_id = None
        for action in bundle.actions:
            if action.target_task_ref and action.target_task_ref.resolved_task_id:
                target_task_id = action.target_task_ref.resolved_task_id
                break

        return ConversationAction(
            action_id=new_id("conv"),
            action_type=ConversationActionType.ACKNOWLEDGE,
            target_task_id=target_task_id,
            urgency=Urgency.NORMAL,
            metadata=metadata,
        )
