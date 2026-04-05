import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

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
    try:
        snapshot = await session.snapshot()
        await websocket.send_json(snapshot.model_dump(mode="json"))
        while True:
            snapshot = await queue.get()
            await websocket.send_json(snapshot.model_dump(mode="json"))
    except (WebSocketDisconnect, asyncio.CancelledError):
        pass
    finally:
        session.unsubscribe(queue)
