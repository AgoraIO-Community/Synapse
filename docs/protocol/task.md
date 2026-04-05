# Task Protocol

`Task` is the durable user-visible work item.

Typical fields:

- `task_id`
- `root_task_id`
- `parent_task_id`
- `title`
- `goal`
- `status`
- `priority`
- `requires_confirmation`
- `interruptible`
- `depends_on_task_ids`
- `session_affinity`
- `task_revision`
- `latest_instruction`

Ownership:

- Communication Brain manipulates task intent through tools
- Execution Brain reads task state and updates execution-related projections

`Task` should not be the main home for:

- raw executor logs
- session internals
- low-level execution history
