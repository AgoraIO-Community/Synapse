# Interruption Protocol

Interruption should be modeled explicitly.

Important dimensions:

- interruption scope
- execution effect
- conversational effect

Suggested scopes:

- `speech_only`
- `task_update`
- `task_control`
- `task_preempt`

Suggested execution effects:

- `none`
- `soft_pause`
- `replan_required`
- `cancel_run`
- `release_session`

Suggested conversational effects:

- `stop_output`
- `ack_and_listen`
- `ask_clarification`
- `ack_and_switch`

Core default:

- stop speaking first
- only affect execution when intent clearly requires it
