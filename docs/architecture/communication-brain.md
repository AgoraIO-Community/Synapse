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
- internal runtime vocabulary should stay hidden unless the user explicitly asks for it

Primary tool surface:

- `create_task`
- `update_task`
- `control_task`
- `add_task_note`
- `add_constraint`
- `list_relevant_tasks`
- `query_task_summary`
- `query_task_detail`

Related docs:

- [../protocol/task.md](../protocol/task.md)
- [../protocol/mutation-and-command.md](../protocol/mutation-and-command.md)
- [Notifications and Interruptions](./notifications-and-interruptions.md)
