# Communication Brain

The Communication Brain owns:

- acknowledgement
- clarification
- direct conversational replies
- task reference resolution
- task manipulation through tools
- reading stable task summaries and details

It does not own:

- executor scheduling
- session lifecycle
- raw execution log interpretation

Core communication policy:

- tool success is an internal fact
- user-facing replies should express action commitment
- default replies should sound like a human accepting and starting work
- bounded user-visible message history is the authoritative conversation state for follow-up context
- OpenAI-backed communication should use a traditional OpenAI-compatible chat-completions loop and replay local user-visible history each turn
- in-flight assistant replies may stream over the session websocket as transient `assistant_response_*` events while only the final assistant reply is persisted
- communication-model tool calls stay internal to the runtime and are not exposed on the frontend websocket contract
- internal runtime vocabulary should stay hidden unless the user explicitly asks for it
- invalid tool arguments from the model should be returned through the tool loop for correction instead of crashing the message transport
- invalid executor ids should be rejected before task creation, and pre-existing bad tasks should fail cleanly rather than crashing execution

Primary tool surface:

- `create_task`
- `update_task`
- `control_task`
- `add_task_note`
- `add_constraint`
- `list_relevant_tasks`
- `query_task_summary`
- `query_task_detail`

`control_task.command_type` must use the canonical protocol values from
[`TaskCommandType`](../protocol/mutation-and-command.md), for example `resume_task`
rather than `resume`.

Related docs:

- [../protocol/task.md](../protocol/task.md)
- [../protocol/mutation-and-command.md](../protocol/mutation-and-command.md)
- [Notifications and Interruptions](./notifications-and-interruptions.md)
