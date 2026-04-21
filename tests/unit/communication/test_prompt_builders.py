import json

from synapse.communication.context import CommunicationContext, CommunicationTaskBrief, ExecutorRuntimeSummary
from synapse.communication.history import ConversationEntry
from synapse.communication.prompts import build_notification_messages, build_reply_messages
from synapse.protocol import (
    NotificationCandidate,
    NotificationCandidateType,
    NotificationPriority,
    Task,
    TaskExecutionDetailEntry,
    TaskStatus,
    TaskSummary,
)


def _build_context(
    *,
    has_real_executor: bool,
    recent_history: list[ConversationEntry] | None = None,
    tasks: list[Task] | None = None,
    summaries: dict[str, TaskSummary | None] | None = None,
    task_execution_details: dict[str, list[TaskExecutionDetailEntry]] | None = None,
    focused_task_ids: list[str] | None = None,
) -> CommunicationContext:
    return CommunicationContext(
        conversation_id="conv-1",
        recent_history=recent_history
        or [
            ConversationEntry(role="user", text="hello"),
            ConversationEntry(role="assistant", text="hi there"),
        ],
        tasks=tasks or [],
        summaries=summaries or {},
        task_execution_details=task_execution_details or {},
        focused_task_ids=focused_task_ids or [],
        focused_tasks=[
            CommunicationTaskBrief(
                task_id=task.task_id,
                title=task.title,
                goal=task.goal,
                status=task.status.value,
                priority=task.priority,
                latest_instruction=task.latest_instruction,
                conversational_summary=(summaries or {}).get(task.task_id).conversational_summary if (summaries or {}).get(task.task_id) else None,
                latest_user_visible_status=(summaries or {}).get(task.task_id).latest_user_visible_status if (summaries or {}).get(task.task_id) else None,
                note_count=0,
                constraint_count=0,
            )
            for task in (tasks or [])
            if task.task_id in (focused_task_ids or [])
        ],
        active_tasks=[],
        recent_tasks=[],
        executor_runtime=ExecutorRuntimeSummary(
            has_real_executor=has_real_executor,
            available_executor_types=["codex"] if has_real_executor else ["mock"],
            default_executor_type="codex" if has_real_executor else "mock",
            executors=[],
        ),
        available_tools=["create_task", "query_task_summary"],
    )


def test_build_reply_messages_keeps_expected_message_shape():
    context = _build_context(has_real_executor=False)

    messages = build_reply_messages(user_text="Draft email", context=context)

    assert [message["role"] for message in messages] == [
        "system",
        "system",
        "system",
        "system",
        "system",
        "system",
        "system",
        "user",
        "assistant",
    ]
    assert "Communication Brain" in messages[0]["content"]
    assert "Tool-selection policy" in messages[1]["content"]
    assert "Fact-checking, claim verification" in messages[1]["content"]
    assert "spoken-language friendly" in messages[2]["content"]
    assert "Do not expose internal tool names" in messages[3]["content"]
    assert "The latest user message is: Draft email" in messages[4]["content"]
    assert "current external information" in messages[4]["content"]
    assert "forget it" in messages[4]["content"]
    assert "focused_tasks" in messages[4]["content"]
    assert "Available tools: create_task, query_task_summary" in messages[4]["content"]
    assert "Examples:" in messages[5]["content"]
    assert "What is the weather?" in messages[5]["content"]
    assert "which city should I check?" in messages[5]["content"]
    assert "Help me find flights from Shanghai to Beijing tomorrow." in messages[5]["content"]
    assert "Forget it." in messages[5]["content"]
    assert "It should be Shanghai." in messages[5]["content"]
    assert "cancel_task" in messages[5]["content"]
    assert "How do I seem today?" in messages[5]["content"]
    assert "What is the weather in Shanghai today?" not in messages[5]["content"]
    assert "Can you fact-check this claim for me?" not in messages[5]["content"]
    assert "What's the stock price today?" not in messages[5]["content"]
    assert json.loads(messages[6]["content"]) == {
        "conversation_id": "conv-1",
        "focused_task_ids": [],
        "focused_tasks": [],
        "active_tasks": [],
        "recent_tasks": [],
        "task_execution_details": {},
        "executor_runtime": {
            "has_real_executor": False,
            "available_executor_types": ["mock"],
            "default_executor_type": "mock",
            "executors": [],
        },
        "available_tools": ["create_task", "query_task_summary"],
    }
    assert messages[7] == {
        "role": "user",
        "content": "hello",
    }
    assert messages[8] == {
        "role": "assistant",
        "content": "hi there",
    }


def test_build_reply_messages_switches_tool_policy_for_real_executor():
    mock_only_messages = build_reply_messages(
        user_text="check cpu",
        context=_build_context(has_real_executor=False),
    )
    real_executor_messages = build_reply_messages(
        user_text="check cpu",
        context=_build_context(has_real_executor=True),
    )

    assert "Only the mock executor is available." in mock_only_messages[1]["content"]
    assert "check a website or app" in mock_only_messages[1]["content"]
    assert "At least one real executor is available" in real_executor_messages[1]["content"]
    assert "Preferred tool: create_task" in real_executor_messages[5]["content"]
    assert "Check my PC CPU usage." in real_executor_messages[5]["content"]
    assert "fact-check whether this quote is authentic" not in real_executor_messages[5]["content"]
    assert "help me draft an email reply" not in mock_only_messages[5]["content"]
    assert "What is the weather in Shanghai today?" not in mock_only_messages[5]["content"]


def test_build_reply_messages_serializes_execution_details():
    messages = build_reply_messages(
        user_text="status?",
        context=_build_context(
            has_real_executor=True,
            task_execution_details={
                "task-1": [
                    TaskExecutionDetailEntry(
                        detail_id="detail-1",
                        task_id="task-1",
                        run_id="run-1",
                        execution_session_id="session-1",
                        event_type="progress",
                        text="meaningful progress",
                        created_at="2026-04-21T00:00:01+00:00",
                    )
                ]
            },
        ),
    )

    runtime_context = json.loads(messages[6]["content"])
    assert runtime_context["task_execution_details"] == {
        "task-1": [
            {
                "run_id": "run-1",
                "execution_session_id": "session-1",
                "event_type": "progress",
                "text": "meaningful progress",
                "created_at": "2026-04-21T00:00:01+00:00",
            }
        ]
    }


def test_build_reply_messages_uses_clarification_examples_for_missing_live_data_operands():
    messages = build_reply_messages(
        user_text="what is the weather?",
        context=_build_context(has_real_executor=True),
    )

    assert "ask one short clarification first" in messages[4]["content"]
    assert "What is the weather?" in messages[5]["content"]
    assert "missing location" in messages[5]["content"]
    assert "Add one note to that email task: keep the tone shorter." in messages[5]["content"]
    assert "Do not send that task yet." in messages[5]["content"]
    assert "Where is that task now?" in messages[5]["content"]


def test_build_notification_messages_contains_candidates_payload_and_history():
    trip_task = Task(
        task_id="task-trip",
        root_task_id="task-trip",
        title="Beijing trip planner",
        goal="Find flights and hotels for Beijing",
        status=TaskStatus.RUNNING,
    )
    weather_task = Task(
        task_id="task-weather",
        root_task_id="task-weather",
        title="Shanghai weather",
        goal="Check the current weather in Shanghai",
        status=TaskStatus.COMPLETED,
    )
    context = _build_context(
        has_real_executor=True,
        recent_history=[
            ConversationEntry(role="user", text="have you checked the weather?"),
            ConversationEntry(role="assistant", text="The current weather in Shanghai is clear."),
        ],
        tasks=[trip_task, weather_task],
        summaries={
            "task-trip": TaskSummary(
                task_id="task-trip",
                conversational_summary="I found flight and hotel options for Beijing.",
                latest_user_visible_status="running",
            )
        },
    )
    candidates = [
        NotificationCandidate(
            candidate_id="cand-1",
            task_id="task-trip",
            candidate_type=NotificationCandidateType.COMPLETED,
            priority=NotificationPriority.P1,
            summary_short="I found flight and hotel options for Beijing.",
            created_at="2026-04-06T00:00:00Z",
            merge_key="completed_digest",
        )
    ]

    messages = build_notification_messages(context=context, candidates=candidates)

    assert [message["role"] for message in messages] == [
        "system",
        "system",
        "system",
        "system",
        "system",
        "system",
        "system",
    ]
    assert "Communication Brain" in messages[0]["content"]
    assert "spoken-language friendly" in messages[1]["content"]
    assert "Do not expose internal tool names" in messages[2]["content"]
    assert "You are generating one proactive assistant update" in messages[3]["content"]
    assert "Do not use markdown" in messages[3]["content"]
    assert "Use notification_candidates, key_task, and relevant_tasks" in messages[3]["content"]
    assert "Do not use tools." in messages[3]["content"]
    assert "Examples:" in messages[4]["content"]
    assert "The email draft is ready. I haven't sent it yet." in messages[4]["content"]
    assert "Quick update: I found a few flight options" in messages[4]["content"]
    assert "This is blocked for the moment." in messages[4]["content"]
    assert json.loads(messages[5]["content"]) == {
        "recent_chat_history": [
            {"role": "user", "text": "have you checked the weather?"},
            {"role": "assistant", "text": "The current weather in Shanghai is clear."},
        ],
        "key_task": {
            "task_id": "task-trip",
            "title": "Beijing trip planner",
            "goal": "Find flights and hotels for Beijing",
            "status": "running",
            "priority": 5,
            "latest_instruction": None,
            "conversational_summary": "I found flight and hotel options for Beijing.",
            "latest_user_visible_status": "running",
            "note_count": 0,
            "constraint_count": 0,
        },
        "relevant_tasks": [
            {
                "task_id": "task-trip",
                "title": "Beijing trip planner",
                "goal": "Find flights and hotels for Beijing",
                "status": "running",
                "priority": 5,
                "latest_instruction": None,
                "conversational_summary": "I found flight and hotel options for Beijing.",
                "latest_user_visible_status": "running",
                "note_count": 0,
                "constraint_count": 0,
            }
        ],
    }
    assert json.loads(messages[6]["content"]) == {
        "notification_candidates": [
            {
                "candidate_type": "completed",
                "task_id": "task-trip",
                "summary_short": "I found flight and hotel options for Beijing.",
                "priority": "p1",
            }
        ]
    }
    assert "task-weather" not in messages[5]["content"]


def test_build_notification_messages_uses_newest_candidate_as_key_task_for_merged_group():
    older_task = Task(
        task_id="task-older",
        root_task_id="task-older",
        title="Weather task",
        goal="Check Shanghai weather",
        status=TaskStatus.COMPLETED,
    )
    newer_task = Task(
        task_id="task-newer",
        root_task_id="task-newer",
        title="Trip planner",
        goal="Check flights and hotels to Beijing",
        status=TaskStatus.RUNNING,
    )
    context = _build_context(
        has_real_executor=True,
        tasks=[older_task, newer_task],
        summaries={
            "task-older": TaskSummary(
                task_id="task-older",
                conversational_summary="The Shanghai weather is clear.",
            ),
            "task-newer": TaskSummary(
                task_id="task-newer",
                conversational_summary="I found flight options to Beijing.",
            ),
        },
    )
    candidates = [
        NotificationCandidate(
            candidate_id="cand-1",
            task_id="task-older",
            candidate_type=NotificationCandidateType.COMPLETED,
            priority=NotificationPriority.P1,
            summary_short="The Shanghai weather is clear.",
            created_at="2026-04-06T00:00:00Z",
            merge_key="completed_digest",
        ),
        NotificationCandidate(
            candidate_id="cand-2",
            task_id="task-newer",
            candidate_type=NotificationCandidateType.COMPLETED,
            priority=NotificationPriority.P1,
            summary_short="I found flight options to Beijing.",
            created_at="2026-04-06T00:00:01Z",
            merge_key="completed_digest",
        ),
    ]

    messages = build_notification_messages(context=context, candidates=candidates)
    rendering_context = json.loads(messages[5]["content"])

    assert rendering_context["key_task"]["task_id"] == "task-newer"
    assert [task["task_id"] for task in rendering_context["relevant_tasks"]] == [
        "task-newer",
        "task-older",
    ]
