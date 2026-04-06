import asyncio
from uuid import uuid4

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from synopse.api.models import SendCommandSocketAction, SendMessageSocketAction
from synopse.communication.resolver import TaskResolver, describe_candidates
from synopse.protocol import TaskCommand

router = APIRouter()


@router.websocket("/sessions/{session_id}/stream")
async def session_stream(websocket: WebSocket, session_id: str):
    container = websocket.app.state.runtime_container
    try:
        session = container.get_session(session_id)
    except KeyError:
        await websocket.close(code=4404)
        return

    await websocket.accept()
    queue = session.subscribe()
    await websocket.send_json((await session.initial_snapshot_event()).model_dump(mode="json"))
    sender = asyncio.create_task(_send_events(websocket, queue))
    try:
        while True:
            payload = await websocket.receive_json()
            await _handle_client_action(session, queue, payload)
    except (WebSocketDisconnect, asyncio.CancelledError):
        pass
    finally:
        sender.cancel()
        try:
            await sender
        except (asyncio.CancelledError, RuntimeError, WebSocketDisconnect):
            pass
        session.unsubscribe(queue)


async def _send_events(websocket: WebSocket, queue: asyncio.Queue) -> None:
    while True:
        event = await queue.get()
        await websocket.send_json(event.model_dump(mode="json"))


async def _handle_client_action(session, queue: asyncio.Queue, payload: object) -> None:
    if not isinstance(payload, dict):
        session.observability.api.ws_action_rejected(
            conversation_id=session.session_id,
            request_id="",
            action_type="unknown",
            error_code="invalid_payload",
        )
        await session.publish_private_event(
            queue,
            session.action_rejected_event(
                "",
                action_type="unknown",
                error_code="invalid_payload",
                message="Socket action payload must be an object.",
            ),
        )
        return

    action_type = payload.get("type")
    request_id = payload.get("request_id")
    request_id_value = request_id if isinstance(request_id, str) else ""
    action_type_value = action_type if isinstance(action_type, str) else "unknown"

    if action_type_value == "send_message":
        await _handle_send_message(session, queue, payload)
        return
    if action_type_value == "send_command":
        await _handle_send_command(session, queue, payload)
        return

    await session.publish_private_event(
        queue,
        session.action_rejected_event(
            request_id_value,
            action_type=action_type_value,
            error_code="unknown_action_type",
            message="Unknown websocket action type.",
        ),
    )
    session.observability.api.ws_action_rejected(
        conversation_id=session.session_id,
        request_id=request_id_value,
        action_type=action_type_value,
        error_code="unknown_action_type",
    )


async def _handle_send_message(session, queue: asyncio.Queue, payload: dict[str, object]) -> None:
    try:
        action = SendMessageSocketAction.model_validate(payload)
    except ValidationError as exc:
        session.observability.api.ws_action_rejected(
            conversation_id=session.session_id,
            request_id=_request_id_from_payload(payload),
            action_type="send_message",
            error_code="invalid_payload",
        )
        await session.publish_private_event(
            queue,
            session.action_rejected_event(
                _request_id_from_payload(payload),
                action_type="send_message",
                error_code="invalid_payload",
                message=str(exc),
            ),
        )
        return

    text = action.text.strip()
    if not text:
        session.observability.api.ws_action_rejected(
            conversation_id=session.session_id,
            request_id=action.request_id,
            action_type=action.type,
            error_code="invalid_message_text",
        )
        await session.publish_private_event(
            queue,
            session.action_rejected_event(
                action.request_id,
                action_type=action.type,
                error_code="invalid_message_text",
                message="Message text must not be empty.",
            ),
        )
        return

    await session.submit_message(action.request_id, text, start_processing=False)
    session.observability.api.message_accepted(
        conversation_id=session.session_id,
        request_id=action.request_id,
        transport="websocket",
    )
    await session.publish_private_event(
        queue,
        session.action_accepted_event(
            action.request_id,
            action_type=action.type,
        ),
    )
    session.observability.api.ws_action_accepted(
        conversation_id=session.session_id,
        request_id=action.request_id,
        action_type=action.type,
    )
    await session.publish_snapshot()
    session.start_message_processing()


async def _handle_send_command(session, queue: asyncio.Queue, payload: dict[str, object]) -> None:
    try:
        action = SendCommandSocketAction.model_validate(payload)
    except ValidationError as exc:
        session.observability.api.ws_action_rejected(
            conversation_id=session.session_id,
            request_id=_request_id_from_payload(payload),
            action_type="send_command",
            error_code="invalid_payload",
        )
        await session.publish_private_event(
            queue,
            session.action_rejected_event(
                _request_id_from_payload(payload),
                action_type="send_command",
                error_code="invalid_payload",
                message=str(exc),
            ),
        )
        return

    tasks = await session.blackboard.list_tasks()
    resolution = TaskResolver().resolve(tasks, task_id=action.task_id, reference=action.reference)
    if resolution.status == "ambiguous":
        session.observability.api.ws_action_rejected(
            conversation_id=session.session_id,
            request_id=action.request_id,
            action_type=action.type,
            error_code="ambiguous_reference",
        )
        await session.publish_private_event(
            queue,
            session.action_rejected_event(
                action.request_id,
                action_type=action.type,
                error_code="ambiguous_reference",
                message=(
                    "Task reference is ambiguous. Relevant tasks: "
                    f"{describe_candidates(resolution.candidates)}."
                ),
            ),
        )
        return
    task = resolution.task
    if task is None:
        session.observability.api.ws_action_rejected(
            conversation_id=session.session_id,
            request_id=action.request_id,
            action_type=action.type,
            error_code="task_not_found",
        )
        await session.publish_private_event(
            queue,
            session.action_rejected_event(
                action.request_id,
                action_type=action.type,
                error_code="task_not_found",
                message="Task not found.",
            ),
        )
        return

    command = TaskCommand(
        command_id=f"cmd-{uuid4().hex[:8]}",
        task_id=task.task_id,
        command_type=action.command_type,
        payload=action.payload,
        created_by="api",
        reason=action.reason,
    )
    await session.publish_private_event(
        queue,
        session.action_accepted_event(
            action.request_id,
            action_type=action.type,
        ),
    )
    session.observability.api.ws_action_accepted(
        conversation_id=session.session_id,
        request_id=action.request_id,
        action_type=action.type,
    )
    session.observability.api.command_accepted(
        conversation_id=session.session_id,
        request_id=action.request_id,
        task_id=task.task_id,
        command_type=action.command_type.value,
        transport="websocket",
    )
    await session.apply_command(command)
    session.schedule_execution()
    await session.publish_snapshot()


def _request_id_from_payload(payload: dict[str, object]) -> str:
    request_id = payload.get("request_id")
    return request_id if isinstance(request_id, str) else ""
