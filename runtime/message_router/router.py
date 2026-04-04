from __future__ import annotations

from runtime.llm.interpreter import InterpreterClient
from runtime.protocols.conversation import UserMessage
from runtime.protocols.runtime import ActionBundle, RoutingDecision
from runtime.protocols.stream import SessionSnapshot


class MessageRouter:
    def __init__(self, interpreter: InterpreterClient) -> None:
        self._interpreter = interpreter

    def route(
        self, user_message: UserMessage, snapshot: SessionSnapshot
    ) -> tuple[RoutingDecision, ActionBundle]:
        return self._interpreter.interpret(
            message_id=user_message.message_id,
            text=user_message.text,
            snapshot=snapshot,
        )
