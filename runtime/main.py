from __future__ import annotations

from dataclasses import dataclass

from fastapi import FastAPI

from runtime.api.commands import router as commands_router
from runtime.api.messages import router as messages_router
from runtime.api.sessions import router as sessions_router
from runtime.api.stream import router as stream_router
from runtime.api.trace import router as trace_router
from runtime.action_router.action_router import ActionRouter
from runtime.communication_brain.event_to_response import EventToResponseMapper
from runtime.communication_brain.interaction_policy import InteractionPolicy
from runtime.communication_brain.response_generator import ResponseGenerator
from runtime.executors.mock import MockExecutor
from runtime.executors.registry import ExecutorRegistry
from runtime.execution_brain.executor_adapter_router import ExecutorAdapterRouter
from runtime.execution_brain.orchestrator import ExecutionOrchestrator
from runtime.infrastructure.config import Settings, load_settings
from runtime.llm.client import LLMServices
from runtime.shared_blackboard.runtime_state import RuntimeStateStore
from runtime.shared_blackboard.trace_state import TraceStateStore


@dataclass(slots=True)
class AppServices:
    settings: Settings
    runtime_state_store: RuntimeStateStore
    trace_state_store: TraceStateStore
    llm_services: LLMServices
    action_router: ActionRouter
    interaction_policy: InteractionPolicy
    execution_orchestrator: ExecutionOrchestrator


def build_services(llm_services: LLMServices | None = None) -> AppServices:
    settings = load_settings()
    runtime_state_store = RuntimeStateStore()
    trace_state_store = TraceStateStore()
    llm_services = llm_services or LLMServices(settings, trace_state_store=trace_state_store)
    if getattr(llm_services.message_interpreter, "_trace_state_store", None) is None:
        llm_services.message_interpreter._trace_state_store = trace_state_store
    action_router = ActionRouter(llm_services.message_interpreter, trace_state_store)
    interaction_policy = InteractionPolicy()
    event_to_response_mapper = EventToResponseMapper()
    response_generator = ResponseGenerator(llm_services.responder)
    registry = ExecutorRegistry()
    registry.register(
        settings.default_executor_id,
        MockExecutor(settings, executor_id=settings.default_executor_id),
    )
    executor_adapter_router = ExecutorAdapterRouter(registry, settings.default_executor_id)
    execution_orchestrator = ExecutionOrchestrator(
        runtime_state_store=runtime_state_store,
        trace_state_store=trace_state_store,
        registry=registry,
        executor_adapter_router=executor_adapter_router,
        event_to_response_mapper=event_to_response_mapper,
        response_generator=response_generator,
    )
    return AppServices(
        settings=settings,
        runtime_state_store=runtime_state_store,
        trace_state_store=trace_state_store,
        llm_services=llm_services,
        action_router=action_router,
        interaction_policy=interaction_policy,
        execution_orchestrator=execution_orchestrator,
    )


def create_app() -> FastAPI:
    app = FastAPI(title="Synopse")
    app.include_router(sessions_router)
    app.include_router(messages_router)
    app.include_router(commands_router)
    app.include_router(stream_router)
    app.include_router(trace_router)

    @app.on_event("startup")
    async def startup() -> None:
        app.state.services = build_services()

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
