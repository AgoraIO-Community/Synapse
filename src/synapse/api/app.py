from __future__ import annotations

from fastapi import FastAPI

from synapse.api.logging import install_access_log_filters
from synapse.api.routes.commands import router as commands_router
from synapse.api.routes.health import router as health_router
from synapse.api.routes.messages import router as messages_router
from synapse.api.routes.sessions import router as sessions_router
from synapse.api.ws.stream import router as stream_router
from synapse.runtime.bootstrap import build_runtime_container


def create_app() -> FastAPI:
    app = FastAPI(title="Synapse v2")
    app.state.runtime_container = build_runtime_container()
    install_access_log_filters(app.state.runtime_container.settings)
    app.include_router(health_router)
    app.include_router(sessions_router)
    app.include_router(messages_router)
    app.include_router(commands_router)
    app.include_router(stream_router)

    return app


app = create_app()
