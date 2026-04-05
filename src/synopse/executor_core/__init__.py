"""Executor core package scaffold."""

from .capabilities import ExecutorCapabilities
from .events import ExecutorEvent, ExecutorEventType
from .executor import Executor
from .registry import ExecutorRegistry
from .results import ExecutorResult
from .session import ExecutorSession

__all__ = [
    "Executor",
    "ExecutorCapabilities",
    "ExecutorEvent",
    "ExecutorEventType",
    "ExecutorRegistry",
    "ExecutorResult",
    "ExecutorSession",
]
