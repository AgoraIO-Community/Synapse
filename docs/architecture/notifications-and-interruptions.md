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
- notification policy decides whether to send, merge, or defer before any wording is generated
- selected notification facts may be rendered into final natural wording later, but delivery policy itself should stay rule-driven
- notification rendering should use candidate-linked structured context with a key task and relevant task list, not broad replayed session history as the factual source
- recent chat history in notification rendering is continuity context only and must not override the selected task facts
- emitted notification wording should stay plain-text and spoken-style, without markdown or list formatting
- first-version delivery focuses on `completed`, `blocked`, and `needs_input`
- first-version turn-taking is basic: defer while assistant output is active and prefer a short merge window for ordinary completion updates

Interruption rules:

- `barge-in` first stops current output
- `barge-in` does not cancel tasks by default
- only explicit task-control or task-update intent should affect execution
- user speech and current assistant speech both take precedence over proactive notification delivery

Interruption classes:

- `speech_only`
- `task_update`
- `task_control`
- `task_preempt`

Conversation-history rules:

- keep internal history separate from user-visible history
- unfinished assistant output may be truncated
- completed assistant messages should not be silently rewritten
- emitted proactive messages are appended as normal assistant turns in the same user-visible persona

Related docs:

- [../protocol/summary-notification.md](../protocol/summary-notification.md)
- [../protocol/interruption.md](../protocol/interruption.md)
