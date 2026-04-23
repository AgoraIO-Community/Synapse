from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from synapse.api.logging import install_access_log_filters
from synapse.api.routes.commands import router as commands_router
from synapse.api.routes.executor_nodes import router as executor_nodes_router
from synapse.api.routes.health import router as health_router
from synapse.api.routes.interaction_requests import router as interaction_requests_router
from synapse.api.routes.messages import router as messages_router
from synapse.api.routes.personas import router as personas_router
from synapse.api.routes.session_config import router as session_config_router
from synapse.api.routes.sessions import router as sessions_router
from synapse.api.ws.executors import router as executor_control_router
from synapse.api.ws.stream import router as stream_router
from synapse.runtime.bootstrap import build_runtime_container
from synapse.runtime.config import Settings


def create_app(*, settings: Settings | None = None) -> FastAPI:
    container = build_runtime_container(settings=settings)
    app = FastAPI(title="Synapse v2")
    app.state.runtime_container = container

    install_access_log_filters(container.settings)
    if container.settings.cors_allowed_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=list(container.settings.cors_allowed_origins),
            allow_methods=["*"],
            allow_headers=["*"],
        )
    app.include_router(health_router)
    app.include_router(sessions_router)
    app.include_router(messages_router)
    app.include_router(commands_router)
    app.include_router(interaction_requests_router)
    app.include_router(personas_router)
    app.include_router(executor_nodes_router)
    app.include_router(session_config_router)
    app.include_router(stream_router)
    app.include_router(executor_control_router)

    return app


app = create_app()
