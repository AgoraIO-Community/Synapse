from __future__ import annotations

from app.llm.responder import ResponseClient
from app.protocols.conversation import ConversationAction


class ResponseGenerator:
    def __init__(self, responder: ResponseClient) -> None:
        self._responder = responder

    def finalize(self, action: ConversationAction) -> ConversationAction:
        if not action.render_text:
            action.render_text = self._responder.render(action)
        return action
