from __future__ import annotations

from dataclasses import dataclass

from fastapi import FastAPI

from app.api.commands import router as commands_router
from app.api.messages import router as messages_router
from app.api.sessions import router as sessions_router
from app.api.stream import router as stream_router
from app.communication_brain.dialog_manager import DialogManager
from app.communication_brain.interpreter import CommunicationInterpreter
from app.communication_brain.response_generator import ResponseGenerator
from app.executors.mock import MockExecutor
from app.executors.registry import ExecutorRegistry
from app.execution_brain.executor_router import ExecutorRouter
from app.execution_brain.orchestrator import ExecutionOrchestrator
from app.infrastructure.config import Settings, load_settings
from app.llm.client import LLMServices
from app.message_router.router import MessageRouter
from app.shared_blackboard.store import SharedBlackboardStore


@dataclass(slots=True)
class AppServices:
    settings: Settings
    store: SharedBlackboardStore
    llm_services: LLMServices
    message_router: MessageRouter
    communication_interpreter: CommunicationInterpreter
    execution_orchestrator: ExecutionOrchestrator


def build_services() -> AppServices:
    settings = load_settings()
    store = SharedBlackboardStore()
    llm_services = LLMServices()
    message_router = MessageRouter(llm_services.interpreter)
    communication_interpreter = CommunicationInterpreter()
    dialog_manager = DialogManager()
    response_generator = ResponseGenerator(llm_services.responder)
    registry = ExecutorRegistry()
    registry.register(
        settings.default_executor_id,
        MockExecutor(settings, executor_id=settings.default_executor_id),
    )
    executor_router = ExecutorRouter(registry, settings.default_executor_id)
    execution_orchestrator = ExecutionOrchestrator(
        store=store,
        registry=registry,
        executor_router=executor_router,
        dialog_manager=dialog_manager,
        response_generator=response_generator,
    )
    return AppServices(
        settings=settings,
        store=store,
        llm_services=llm_services,
        message_router=message_router,
        communication_interpreter=communication_interpreter,
        execution_orchestrator=execution_orchestrator,
    )


def create_app() -> FastAPI:
    app = FastAPI(title="Synopse")
    app.state.services = build_services()
    app.include_router(sessions_router)
    app.include_router(messages_router)
    app.include_router(commands_router)
    app.include_router(stream_router)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
