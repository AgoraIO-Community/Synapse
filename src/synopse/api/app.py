from __future__ import annotations

from fastapi import FastAPI

from synopse.api.routes.commands import router as commands_router
from synopse.api.routes.health import router as health_router
from synopse.api.routes.messages import router as messages_router
from synopse.api.routes.sessions import router as sessions_router
from synopse.api.ws.stream import router as stream_router
from synopse.runtime.bootstrap import build_runtime_container


def create_app() -> FastAPI:
    app = FastAPI(title="Synopse v2")
    app.state.runtime_container = build_runtime_container()
    app.include_router(health_router)
    app.include_router(sessions_router)
    app.include_router(messages_router)
    app.include_router(commands_router)
    app.include_router(stream_router)

    return app


app = create_app()
