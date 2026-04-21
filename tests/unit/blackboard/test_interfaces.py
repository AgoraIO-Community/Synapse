from synapse.blackboard import BlackboardStore


def test_blackboard_store_protocol_exposes_expected_methods():
    expected_methods = [
        "put_task",
        "get_task",
        "list_tasks",
        "append_mutation",
        "list_mutations",
        "append_command",
        "list_commands",
        "put_run",
        "get_run",
        "put_session",
        "get_session",
        "put_binding",
        "get_binding",
        "put_summary",
        "get_summary",
        "put_execution_mode",
        "get_execution_mode",
        "list_execution_modes",
        "put_notification_candidate",
        "get_notification_candidate",
        "list_notification_candidates",
        "put_interaction_request",
        "get_interaction_request",
        "list_interaction_requests",
        "put_attention_item",
        "get_attention_item",
        "list_attention_items",
    ]

    for method_name in expected_methods:
        assert hasattr(BlackboardStore, method_name)
