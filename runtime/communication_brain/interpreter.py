from __future__ import annotations

from runtime.infrastructure.ids import new_id
from runtime.protocols.conversation import ConversationAction, ConversationActionType, Urgency
from runtime.protocols.runtime import ActionBundle, RoutingDecision


class CommunicationInterpreter:
    def build_initial_action(
        self, decision: RoutingDecision, bundle: ActionBundle
    ) -> ConversationAction:
        if decision.needs_clarification:
            return ConversationAction(
                action_id=new_id("conv"),
                action_type=ConversationActionType.CLARIFY,
                urgency=Urgency.HIGH,
                reason=decision.clarification_reason,
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
        )
