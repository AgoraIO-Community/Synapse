# Task Protocol

`Task` is the durable user-visible work item.

It is the unified logical work unit for Synapse, rather than one of two separate task systems.

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

Relationship note:

- `Task` is not the same thing as `ExecutionSession`
- execution lineage and live binding are represented separately through execution-session, run, and binding objects

`Task` should not be the main home for:

- raw executor logs
- session internals
- low-level execution history
