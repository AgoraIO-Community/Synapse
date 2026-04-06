# Execution Mode

`TaskExecutionMode` is the stable task-level projection of how Execution Brain currently classifies a task.

Current enum:

- `undecided`
- `lightweight`
- `managed`

`TaskExecutionMode` should include:

- `task_id`
- `mode`
- `decided_from_run_id`
- `elapsed_seconds`

First-version behavior:

- new tasks begin as `undecided`
- terminal runs below the elapsed threshold become `lightweight`
- runs at or above the threshold become `managed`
- transitions only upgrade; they do not automatically downgrade

This projection exists so communication, summary, notification, debugging, and future frontend behavior can all read the same execution-mode fact from blackboard.
