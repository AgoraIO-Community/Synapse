# Communication Brain

The Communication Brain owns:

- acknowledgement
- clarification
- user-intent understanding inside the communication loop
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
- ambiguous task references should not silently fall back to the latest task; the communication brain should resolve them explicitly or ask for clarification
- task-first routing is the default; only clear social, subjective, or Synopse-meta conversation should remain pure chat
- actionable requests should usually become tasks even when phrased as questions
- capability-gated requests such as checking machine state, reading the workspace, or running commands are a high-value subset of those task requests
- if only the mock executor is available, ordinary task requests should be blocked by default unless they are explicitly mock-safe
- there is no standalone message interpreter in the primary `v2` design; interpretation is part of Communication Brain tool use

Primary tool surface:

- `create_task`
- `update_task`
- `control_task`
- `add_task_note`
- `add_constraint`
- `list_tasks`
- `query_task_summary`
- `query_task_detail`

Architecture terminology note:

- `list_tasks` here means the task-retrieval and disambiguation tool used by Communication Brain
- it does not mean an unscoped "dump every task" storage API

Tool intent defaults:

- use `add_task_note` for extra user context, examples, preferences, or clarifications on an existing task
- use `add_constraint` for execution constraints such as deadlines, formatting rules, or do-not-send instructions
- use `update_task` only for core structured task fields such as title, goal, priority, executor preference, or latest instruction
- use `list_tasks` before a write or query when the target task is uncertain
- use `create_task.mock_safe = true` only for explicit simulation, demo, or record-only tasks

`control_task.command_type` must use the canonical protocol values from
[`TaskCommandType`](../protocol/mutation-and-command.md), for example `resume_task`
rather than `resume`.

Related docs:

- [../protocol/task.md](../protocol/task.md)
- [../protocol/mutation-and-command.md](../protocol/mutation-and-command.md)
- [Notifications and Interruptions](./notifications-and-interruptions.md)
