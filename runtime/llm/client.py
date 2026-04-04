from runtime.infrastructure.config import Settings
from runtime.llm.openai_client import OpenAIProvider
from runtime.llm.message_interpreter import MessageInterpreterClient
from runtime.llm.responder import ResponseClient
from runtime.shared_blackboard.trace_state import TraceStateStore


class LLMServices:
    def __init__(
        self,
        settings: Settings,
        provider: OpenAIProvider | None = None,
        trace_state_store: TraceStateStore | None = None,
    ) -> None:
        provider = provider or OpenAIProvider(settings)
        self.message_interpreter = MessageInterpreterClient(provider, trace_state_store)
        self.responder = ResponseClient(provider)
