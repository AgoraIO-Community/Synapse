from app.llm.interpreter import InterpreterClient
from app.llm.responder import ResponseClient


class LLMServices:
    def __init__(self) -> None:
        self.interpreter = InterpreterClient()
        self.responder = ResponseClient()
