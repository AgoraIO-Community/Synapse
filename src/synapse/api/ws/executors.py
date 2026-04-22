from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from synapse.protocol import (
    AckMessage,
    NodeStatusMessage,
    InteractionStateMessage,
    RegisterNodeMessage,
    RunEventMessage,
)
from synapse.runtime.executor_node_manager import ExecutorNodeAuthError

router = APIRouter()


@router.websocket("/executors/control")
async def executor_control(websocket: WebSocket):
    container = websocket.app.state.runtime_container
    await websocket.accept()
    registered = False
    try:
        payload = await websocket.receive_json()
        register = RegisterNodeMessage.model_validate(payload)
        ack = await container.executor_node_manager.register_connection(websocket, register)
        registered = True
        await websocket.send_json(ack.model_dump(mode="json"))
        await container.handle_executor_node_connected()

        while True:
            payload = await websocket.receive_json()
            ack = await _handle_control_message(container, payload)
            await websocket.send_json(ack.model_dump(mode="json"))
    except ValidationError:
        await websocket.close(code=4400)
    except ExecutorNodeAuthError:
        await websocket.close(code=4403)
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        if registered:
            await container.executor_node_manager.disconnect(reason="connection_closed")


async def _handle_control_message(container, payload: object) -> AckMessage:
    if not isinstance(payload, dict):
        return AckMessage(message_type="unknown", ok=False, detail="invalid_payload")
    message_type = payload.get("type")
    if message_type == "run_event":
        return await container.executor_node_manager.publish_run_event(
            RunEventMessage.model_validate(payload)
        )
    if message_type == "interaction_state":
        InteractionStateMessage.model_validate(payload)
        return AckMessage(message_type="interaction_state", detail="ignored")
    if message_type == "node_status":
        NodeStatusMessage.model_validate(payload)
        return AckMessage(message_type="node_status", detail="ok")
    return AckMessage(message_type=str(message_type or "unknown"), ok=False, detail="unknown_message_type")
