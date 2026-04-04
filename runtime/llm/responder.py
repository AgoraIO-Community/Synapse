from __future__ import annotations

from runtime.protocols.conversation import ConversationAction, ConversationActionType


class ResponseClient:
    def render(self, action: ConversationAction) -> str:
        if action.render_text:
            return action.render_text

        match action.action_type:
            case ConversationActionType.ACKNOWLEDGE:
                return "Understood. I am starting that now."
            case ConversationActionType.CLARIFY:
                return action.reason or "I need clarification before I continue."
            case ConversationActionType.ASK_CONFIRMATION:
                return action.reason or "Please confirm before I proceed."
            case ConversationActionType.INFORM_PROGRESS:
                return action.reason or "The task is still running."
            case ConversationActionType.INFORM_BLOCKED:
                return action.reason or "The task is blocked and needs input."
            case ConversationActionType.INFORM_DONE:
                return action.reason or "The task is complete."
            case ConversationActionType.INFORM_FAILED:
                return action.reason or "The task failed."
            case ConversationActionType.INFORM_CANCELED:
                return action.reason or "The task was canceled."
            case ConversationActionType.HOLD:
                return action.reason or "I am keeping the task active in the background."
        return "Acknowledged."
