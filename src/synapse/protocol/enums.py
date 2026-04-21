from __future__ import annotations

from enum import StrEnum


class TaskStatus(StrEnum):
    CREATED = "created"
    QUEUED = "queued"
    RUNNING = "running"
    WAITING_USER_INPUT = "waiting_user_input"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class RunStatus(StrEnum):
    CREATED = "created"
    ASSIGNED = "assigned"
    RUNNING = "running"
    BLOCKED = "blocked"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ExecutionMode(StrEnum):
    UNDECIDED = "undecided"
    LIGHTWEIGHT = "lightweight"
    MANAGED = "managed"


class SessionStatus(StrEnum):
    IDLE = "idle"
    WARM_IDLE = "warm_idle"
    BUSY = "busy"
    SUSPENDED = "suspended"
    TERMINATED = "terminated"


class MutationType(StrEnum):
    CREATE = "create"
    UPDATE = "update"
    CONTROL = "control"
    ADD_TASK_NOTE = "add_task_note"
    ADD_CONSTRAINT = "add_constraint"


class TaskCommandType(StrEnum):
    PAUSE_TASK = "pause_task"
    CANCEL_TASK = "cancel_task"
    PREEMPT_TASK = "preempt_task"
    RESUME_TASK = "resume_task"
    RETRY_TASK = "retry_task"


class NotificationPriority(StrEnum):
    P0 = "p0"
    P1 = "p1"
    P2 = "p2"
    P3 = "p3"


class NotificationCandidateType(StrEnum):
    COMPLETED = "completed"
    BLOCKED = "blocked"
    NEEDS_INPUT = "needs_input"


class NotificationDeliveryStatus(StrEnum):
    PENDING = "pending"
    EMITTED = "emitted"
    SUPPRESSED = "suppressed"


class InteractionRequestKind(StrEnum):
    PERMISSION = "permission"
    QUESTION = "question"
    CONFIRMATION = "confirmation"


class InteractionRequestStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"
    ANSWERED = "answered"
    RESOLVED = "resolved"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class AttentionPriority(StrEnum):
    P0 = "p0"
    P1 = "p1"
    P2 = "p2"
    P3 = "p3"


class AttentionItemKind(StrEnum):
    PERMISSION_REQUEST = "permission_request"
    QUESTION_REQUEST = "question_request"
    CONFIRMATION_REQUEST = "confirmation_request"
    TASK_PAUSED = "task_paused"
    TASK_RESUMED = "task_resumed"
    TASK_BLOCKED = "task_blocked"
    TASK_COMPLETED = "task_completed"


class AttentionItemStatus(StrEnum):
    ACTIVE = "active"
    ACTED = "acted"
    DISMISSED = "dismissed"
    EXPIRED = "expired"


class InterruptionType(StrEnum):
    SPEECH_ONLY = "speech_only"
    TASK_UPDATE = "task_update"
    TASK_CONTROL = "task_control"
    TASK_PREEMPT = "task_preempt"


class ConversationEffect(StrEnum):
    STOP_OUTPUT = "stop_output"
    ACK_AND_LISTEN = "ack_and_listen"
    ASK_CLARIFICATION = "ask_clarification"
    ACK_AND_SWITCH = "ack_and_switch"


class BindingStatus(StrEnum):
    CREATED = "created"
    CLAIMED = "claimed"
    ACTIVE = "active"
    PAUSED = "paused"
    RELEASED = "released"
