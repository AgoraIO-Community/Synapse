from runtime.execution_brain.event_normalizer import apply_execution_event_to_task
from runtime.protocols.execution import ExecutionEvent, ExecutionEventType
from runtime.protocols.tasks import Artifact, Task, TaskStatus


def test_completed_event_updates_task_output_summary_from_text_artifact():
    task = Task(
        task_id="task_1",
        root_task_id="task_1",
        title="Check CPU",
        goal="Check CPU",
    )
    event = ExecutionEvent(
        event_id="exec_1",
        task_id="task_1",
        executor_id="codex_executor",
        event_type=ExecutionEventType.COMPLETED,
        status=TaskStatus.DONE,
        progress_message="Task completed successfully.",
        artifacts_delta=[
            Artifact(
                artifact_id="artifact_1",
                task_id="task_1",
                artifact_type="text",
                name="cpu_result",
                inline_value="CPU usage is currently 23%.",
            )
        ],
    )

    apply_execution_event_to_task(task, event)

    assert task.output_summary == "CPU usage is currently 23%."
    assert task.artifacts[0].inline_value == "CPU usage is currently 23%."
