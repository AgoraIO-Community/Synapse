from __future__ import annotations


class UnsupportedExecutorCommandError(RuntimeError):
    def __init__(self, *, executor_id: str, command_type: str) -> None:
        super().__init__(
            f"Executor '{executor_id}' does not support command '{command_type}'."
        )
        self.executor_id = executor_id
        self.command_type = command_type
