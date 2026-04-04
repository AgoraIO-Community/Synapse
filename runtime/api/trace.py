import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()


@router.websocket("/sessions/{session_id}/trace")
async def session_trace_stream(websocket: WebSocket, session_id: str):
    services = websocket.app.state.services
    try:
        services.runtime_state_store.get_session(session_id)
    except KeyError:
        await websocket.close(code=4404)
        return

    await websocket.accept()
    queue = services.trace_state_store.subscribe(session_id)
    try:
        await services.trace_state_store.publish_snapshot(session_id)
        while True:
            event = await queue.get()
            await websocket.send_json(event.model_dump(mode="json"))
    except (WebSocketDisconnect, asyncio.CancelledError):
        pass
    finally:
        services.trace_state_store.unsubscribe(session_id, queue)
