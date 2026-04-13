# Mutation and Command Protocol

Synapse separates:

- `TaskMutation`
- `TaskCommand`

`TaskMutation` is for structured task changes, such as:

- update title
- add task note
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
- `retry_task`

Communication-model tool calls must use these exact canonical `command_type` tokens.
Short aliases such as `resume` are invalid tool input and should be handled in-band,
not as transport failures.

Communication-brain task resolution should also be explicit:

- ambiguous references should return an in-band tool error
- missing references should return an in-band tool error
- tools should not silently default to the latest task when the target is unclear

Key fields:

- `command_id`
- `task_id`
- `command_type`
- `payload`
- `issued_by`
- `reason`
