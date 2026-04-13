"""Communication Brain package scaffold."""

from .brain import CommunicationBrain, CommunicationTurnResult
from .history import InMemoryConversationHistory

__all__ = ["CommunicationBrain", "CommunicationTurnResult", "InMemoryConversationHistory"]
