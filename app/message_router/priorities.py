from __future__ import annotations

from app.protocols.runtime import RuntimeAction, RuntimeActionType
from app.protocols.tasks import ControlCommandType, Priority


_PRIORITY_WEIGHT = {
    Priority.LOW: 1,
    Priority.NORMAL: 2,
    Priority.HIGH: 3,
    Priority.URGENT: 4,
}

_ACTION_WEIGHT = {
    RuntimeActionType.CONTROL_TASK: 5,
    RuntimeActionType.UPDATE_TASK: 4,
    RuntimeActionType.EMIT_CONVERSATION_ACTION: 3,
    RuntimeActionType.APPLY_CONTEXT_PATCH: 2,
    RuntimeActionType.CREATE_TASK: 1,
}


def _control_bonus(action: RuntimeAction) -> int:
    command_type = action.payload.get("command_type")
    if command_type in {
        ControlCommandType.CANCEL_TASK.value,
        ControlCommandType.PAUSE_TASK.value,
    }:
        return 2
    return 0


def sort_actions(actions: list[RuntimeAction]) -> list[RuntimeAction]:
    return sorted(
        actions,
        key=lambda action: (
            -_PRIORITY_WEIGHT[action.priority],
            -(_ACTION_WEIGHT[action.action_type] + _control_bonus(action)),
        ),
    )
