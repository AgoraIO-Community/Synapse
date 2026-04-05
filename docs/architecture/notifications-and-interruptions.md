# Notifications and Interruptions

`v2` adds a lightweight orchestration layer for:

- proactive notification delivery
- digest aggregation
- turn-taking
- interruption management

Important rules:

- blackboard update does not directly equal assistant speech
- user-visible updates first become notification candidates
- only emitted proactive messages enter user-visible conversation history
- digest-first delivery is preferred over one-event-one-message

Interruption rules:

- `barge-in` first stops current output
- `barge-in` does not cancel tasks by default
- only explicit task-control or task-update intent should affect execution

Interruption classes:

- `speech_only`
- `task_update`
- `task_control`
- `task_preempt`

Conversation-history rules:

- keep internal history separate from user-visible history
- unfinished assistant output may be truncated
- completed assistant messages should not be silently rewritten

Related docs:

- [../protocol/summary-notification.md](../protocol/summary-notification.md)
- [../protocol/interruption.md](../protocol/interruption.md)
