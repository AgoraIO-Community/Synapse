import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()


@router.websocket("/sessions/{session_id}/stream")
async def session_stream(websocket: WebSocket, session_id: str):
    services = websocket.app.state.services
    try:
        services.store.get_session(session_id)
    except KeyError:
        await websocket.close(code=4404)
        return

    await websocket.accept()
    queue = services.store.subscribe(session_id)
    try:
        await services.store.publish_snapshot(session_id)
        while True:
            event = await queue.get()
            await websocket.send_json(event.model_dump(mode="json"))
    except (WebSocketDisconnect, asyncio.CancelledError):
        pass
    finally:
        services.store.unsubscribe(session_id, queue)
