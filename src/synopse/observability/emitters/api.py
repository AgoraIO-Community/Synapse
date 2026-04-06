from __future__ import annotations

from dataclasses import dataclass

from ..logger import DiagnosticLogger


@dataclass(slots=True)
class ApiDiagnosticEmitter:
    logger: DiagnosticLogger

    def session_created(self, *, conversation_id: str) -> None:
        self.logger.emit_event(
            level="INFO",
            event_name="api.session.created",
            component="api.sessions",
            summary="Session created",
            conversation_id=conversation_id,
        )

    def message_accepted(self, *, conversation_id: str, request_id: str, transport: str) -> None:
        self.logger.emit_event(
            level="INFO",
            event_name="api.message.accepted",
            component="api.messages",
            summary="Message accepted",
            conversation_id=conversation_id,
            request_id=request_id,
            details={"transport": transport},
        )

    def command_accepted(
        self,
        *,
        conversation_id: str,
        request_id: str | None,
        task_id: str,
        command_type: str,
        transport: str,
    ) -> None:
        self.logger.emit_event(
            level="INFO",
            event_name="api.command.accepted",
            component="api.commands",
            summary="Command accepted",
            conversation_id=conversation_id,
            request_id=request_id,
            task_id=task_id,
            outcome=command_type,
            details={"transport": transport},
        )

    def ws_action_accepted(
        self,
        *,
        conversation_id: str,
        request_id: str,
        action_type: str,
    ) -> None:
        self.logger.emit_event(
            level="INFO",
            event_name="ws.action.accepted",
            component="api.ws",
            summary="Websocket action accepted",
            conversation_id=conversation_id,
            request_id=request_id,
            outcome=action_type,
        )

    def ws_action_rejected(
        self,
        *,
        conversation_id: str,
        request_id: str,
        action_type: str,
        error_code: str,
    ) -> None:
        self.logger.emit_event(
            level="WARNING",
            event_name="ws.action.rejected",
            component="api.ws",
            summary="Websocket action rejected",
            conversation_id=conversation_id,
            request_id=request_id,
            outcome=action_type,
            reason_code=error_code,
        )
