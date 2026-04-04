from runtime.communication_brain.event_to_response import EventToResponseMapper
from runtime.protocols.execution import ExecutionEvent, ExecutionEventType
from runtime.protocols.tasks import Artifact, TaskStatus


def test_completed_event_prefers_text_artifact_over_generic_completion_message():
    mapper = EventToResponseMapper()
    event = ExecutionEvent(
        event_id="exec_1",
        task_id="task_1",
        executor_id="mock_executor",
        event_type=ExecutionEventType.COMPLETED,
        status=TaskStatus.DONE,
        progress_message="Task completed successfully.",
        artifacts_delta=[
            Artifact(
                artifact_id="artifact_1",
                task_id="task_1",
                artifact_type="text",
                name="summary",
                inline_value="The current time is 19:45.",
            )
        ],
    )

    action = mapper.on_execution_event("session_1", event)

    assert action is not None
    assert action.reason == "The current time is 19:45."
    assert action.metadata["preferred_result_text"] == "The current time is 19:45."
