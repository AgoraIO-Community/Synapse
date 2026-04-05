from runtime.llm.fallback import heuristic_interpretation


def test_heuristic_interpretation_treats_continue_with_context_as_update():
    decision, bundle = heuristic_interpretation(
        message_id="message_1",
        text="continue with the recipient info",
        has_existing_tasks=True,
    )

    assert decision.needs_clarification is False
    assert bundle.actions[0].action_type.value == "update_task"
    assert bundle.actions[0].payload["goal"] == "continue with the recipient info"
    assert bundle.actions[0].payload["title"] == "continue with the recipient info"
    assert bundle.actions[0].payload["latest_instruction"] == "continue with the recipient info"
