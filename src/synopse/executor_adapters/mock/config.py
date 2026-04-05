from __future__ import annotations

from pydantic import BaseModel


class MockExecutorConfig(BaseModel):
    executor_type: str = "mock"
