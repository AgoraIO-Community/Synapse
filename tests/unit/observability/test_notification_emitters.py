from datetime import UTC, datetime

from synapse.communication.model import LlmTraceRecord
from synapse.blackboard import BlackboardWriteEvent, BlackboardWriteKind
from synapse.observability.emitters.blackboard import BlackboardDiagnosticEmitter
from synapse.notification.policy import NotificationDeliveryGroup, NotificationDeliveryPlan
from synapse.observability.emitters.communication import CommunicationDiagnosticEmitter
from synapse.observability.emitters.notification import NotificationDiagnosticEmitter
from synapse.observability.logger import DiagnosticLogger
from synapse.observability.store import InMemoryDiagnosticStore
from synapse.protocol import (
    NotificationCandidate,
    NotificationCandidateType,
    NotificationDeliveryStatus,
    NotificationPriority,
)


def _candidate(
    *,
    candidate_id: str,
    task_id: str,
    created_at: str,
    merge_key: str = "completed_digest",
) -> NotificationCandidate:
    return NotificationCandidate(
        candidate_id=candidate_id,
        task_id=task_id,
        candidate_type=NotificationCandidateType.COMPLETED,
        priority=NotificationPriority.P2,
        summary_short="Done.",
        created_at=created_at,
        delivery_status=NotificationDeliveryStatus.PENDING,
        merge_key=merge_key,
        requires_immediate_delivery=False,
    )


def test_notification_emitter_logs_adopted_plan_details():
    logger = DiagnosticLogger(store=InMemoryDiagnosticStore())
    emitter = NotificationDiagnosticEmitter(logger)
    candidates = [
        _candidate(
            candidate_id="notif-1",
            task_id="task-1",
            created_at="2026-04-06T12:00:00+00:00",
        ),
        _candidate(
            candidate_id="notif-2",
            task_id="task-2",
            created_at="2026-04-06T12:00:01+00:00",
        ),
    ]
    plan = NotificationDeliveryPlan(
        groups=[NotificationDeliveryGroup(candidates=candidates)],
        next_due_seconds=None,
    )

    emitter.plan_adopted(
        policy_name="NotificationPolicy",
        merge_window_seconds=2.0,
        pending_candidates=candidates,
        plan=plan,
        assistant_busy=False,
        has_pending_user_messages=False,
    )

    event = list(logger.store.all())[-1]
    assert event.event_name == "notify.plan.adopted"
    assert event.details["policy_name"] == "NotificationPolicy"
    assert event.details["merge_window_seconds"] == 2.0
    assert event.details["pending_candidate_ids"] == ["notif-1", "notif-2"]
    assert event.details["groups"][0]["candidate_ids"] == ["notif-1", "notif-2"]
    assert event.details["groups"][0]["task_ids"] == ["task-1", "task-2"]


def test_notification_emitter_logs_key_task_for_batch_emitted():
    logger = DiagnosticLogger(store=InMemoryDiagnosticStore())
    emitter = NotificationDiagnosticEmitter(logger)
    candidates = [
        _candidate(
            candidate_id="notif-1",
            task_id="task-1",
            created_at=datetime(2026, 4, 6, 12, 0, 0, tzinfo=UTC).isoformat(),
        )
    ]

    emitter.batch_emitted(
        candidates=candidates,
        key_task_id="task-1",
        relevant_task_ids=["task-1"],
    )

    event = list(logger.store.all())[-1]
    assert event.event_name == "notify.batch.emitted"
    assert event.details["key_task_id"] == "task-1"
    assert event.details["relevant_task_ids"] == ["task-1"]


def test_communication_emitter_logs_notification_trace_summary_fields():
    logger = DiagnosticLogger(store=InMemoryDiagnosticStore())
    emitter = CommunicationDiagnosticEmitter(logger)

    emitter.llm_trace(
        LlmTraceRecord(
            trace_id="trace-1",
            source="notification",
            phase="request_built",
            prompt_sections=["notification_rendering_context", "notification_candidates"],
            messages=[{"role": "system", "content": "payload"}],
            notification_candidates=[
                {
                    "candidate_type": "completed",
                    "task_id": "task-trip",
                    "summary_short": "Trip options ready.",
                    "priority": "p2",
                }
            ],
            notification_key_task_id="task-trip",
            notification_relevant_task_ids=["task-trip", "task-hotel"],
            notification_recent_chat_turn_count=4,
            affected_task_ids=["task-trip"],
        )
    )

    event = list(logger.store.all())[-1]
    assert event.event_name == "notify.llm.request_built"
    assert event.details["notification_key_task_id"] == "task-trip"
    assert event.details["notification_relevant_task_ids"] == ["task-trip", "task-hotel"]
    assert event.details["notification_recent_chat_turn_count"] == 4


def test_communication_emitter_always_logs_system_messages_for_message_request_trace():
    logger = DiagnosticLogger(store=InMemoryDiagnosticStore())
    emitter = CommunicationDiagnosticEmitter(logger)
    long_system_text = "identity " + ("prompt " * 30)

    emitter.llm_trace(
        LlmTraceRecord(
            trace_id="trace-2",
            source="message",
            phase="request_built",
            prompt_sections=["identity", "runtime_context"],
            messages=[
                {"role": "system", "content": long_system_text},
                {"role": "system", "content": "runtime"},
                {"role": "user", "content": "hello"},
            ],
            user_text="hello",
        )
    )

    event = list(logger.store.all())[-1]
    assert event.event_name == "comm.llm.request_built"
    assert event.details["system_messages"] == [
        {"role": "system", "content": long_system_text},
        {"role": "system", "content": "runtime"},
    ]
    assert "messages" not in event.details


def test_communication_emitter_logs_reply_failed_error_details():
    logger = DiagnosticLogger(store=InMemoryDiagnosticStore())
    emitter = CommunicationDiagnosticEmitter(logger)

    emitter.reply_failed(
        conversation_id="conv-1",
        request_id="req-1",
        reason_code="communication_model_failure",
        error_type="JSONDecodeError",
        error_message="Expecting value: line 1 column 1 (char 0)",
    )

    event = list(logger.store.all())[-1]
    assert event.event_name == "comm.reply.failed"
    assert event.reason_code == "communication_model_failure"
    assert event.details["error_type"] == "JSONDecodeError"
    assert "Expecting value" in event.details["error_message"]


def test_blackboard_emitter_demotes_progress_run_updates_to_debug():
    logger = DiagnosticLogger(store=InMemoryDiagnosticStore())
    emitter = BlackboardDiagnosticEmitter(logger)

    emitter.record_write(
        event=BlackboardWriteEvent(
            kind=BlackboardWriteKind.RUN,
            entity_id="run-1",
            task_id="task-1",
            payload={
                "change_kind": "progress_update",
                "status": "running",
                "latest_progress_message": "Working through step 1.",
            },
        ),
        created=False,
    )

    event = list(logger.store.all())[-1]
    assert event.event_name == "bb.run.updated"
    assert event.level == "DEBUG"


def test_blackboard_emitter_keeps_semantic_task_changes_at_info():
    logger = DiagnosticLogger(store=InMemoryDiagnosticStore())
    emitter = BlackboardDiagnosticEmitter(logger)

    emitter.record_write(
        event=BlackboardWriteEvent(
            kind=BlackboardWriteKind.TASK,
            entity_id="task-1",
            task_id="task-1",
            payload={
                "change_kind": "status_change",
                "status": "running",
                "previous_status": "created",
            },
        ),
        created=False,
    )

    event = list(logger.store.all())[-1]
    assert event.event_name == "bb.task.updated"
    assert event.level == "INFO"
