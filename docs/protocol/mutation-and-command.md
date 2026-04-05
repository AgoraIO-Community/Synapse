# Mutation and Command Protocol

Synopse separates:

- `TaskMutation`
- `TaskCommand`

`TaskMutation` is for structured task changes, such as:

- update title
- add constraint
- attach user clarification
- change priority

Key fields:

- `mutation_id`
- `task_id`
- `mutation_type`
- `patch`
- `issued_by`
- `urgency`
- `effective_scope`
- `requires_replan`

`TaskCommand` is for explicit control, such as:

- `pause_task`
- `cancel_task`
- `preempt_task`
- `resume_task`

Key fields:

- `command_id`
- `task_id`
- `command_type`
- `payload`
- `issued_by`
- `reason`
