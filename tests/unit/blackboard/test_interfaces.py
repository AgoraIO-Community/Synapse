from synopse.blackboard import BlackboardStore


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
    ]

    for method_name in expected_methods:
        assert hasattr(BlackboardStore, method_name)
