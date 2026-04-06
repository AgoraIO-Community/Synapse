import json

from synopse.communication.context import CommunicationContext, ExecutorRuntimeSummary
from synopse.communication.history import ConversationEntry
from synopse.communication.prompts import build_notification_messages, build_reply_messages
from synopse.protocol import NotificationCandidate, NotificationCandidateType, NotificationPriority


def _build_context(*, has_real_executor: bool) -> CommunicationContext:
    return CommunicationContext(
        conversation_id="conv-1",
        recent_history=[
            ConversationEntry(role="user", text="hello"),
            ConversationEntry(role="assistant", text="hi there"),
        ],
        tasks=[],
        summaries={},
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
    assert "spoken-language friendly" in messages[2]["content"]
    assert "Do not expose internal tool names" in messages[3]["content"]
    assert "The latest user message is: Draft email" in messages[4]["content"]
    assert "Available tools: create_task, query_task_summary" in messages[4]["content"]
    assert "Examples:" in messages[5]["content"]
    assert json.loads(messages[6]["content"]) == {
        "conversation_id": "conv-1",
        "active_tasks": [],
        "recent_tasks": [],
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
    assert "At least one real executor is available" in real_executor_messages[1]["content"]
    assert "Preferred tool: create_task" in real_executor_messages[5]["content"]


def test_build_notification_messages_contains_candidates_payload_and_history():
    context = _build_context(has_real_executor=True)
    candidates = [
        NotificationCandidate(
            candidate_id="cand-1",
            task_id="task-1",
            candidate_type=NotificationCandidateType.COMPLETED,
            priority=NotificationPriority.P1,
            summary_short="Done.",
            created_at="2026-04-06T00:00:00Z",
            merge_key="task:task-1:completed",
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
        "user",
        "assistant",
    ]
    assert "Communication Brain" in messages[0]["content"]
    assert "spoken-language friendly" in messages[1]["content"]
    assert "Do not expose internal tool names" in messages[2]["content"]
    assert "You are generating one proactive assistant update" in messages[3]["content"]
    assert "Do not use tools." in messages[3]["content"]
    assert "Examples:" in messages[4]["content"]
    assert json.loads(messages[5]["content"])["conversation_id"] == "conv-1"
    assert json.loads(messages[6]["content"]) == {
        "notification_candidates": [
            {
                "candidate_type": "completed",
                "task_id": "task-1",
                "summary_short": "Done.",
                "priority": "p1",
            }
        ]
    }
