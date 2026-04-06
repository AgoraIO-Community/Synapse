# Execution Brain

The Execution Brain owns:

- runnable-task discovery
- task claim and lease management
- agent session lifecycle
- executor dispatch
- execution-state updates
- summary refresh
- execution classification decisions
- interruption resolution on the execution side

It should be driven by:

- blackboard notifications
- periodic reconciliation

Request handlers should schedule execution work and return promptly.
Long-running executor activity should continue in the background while websocket
subscribers receive updated session snapshots as blackboard state changes.

It should not depend on Communication Brain internals.
It should not generate final user-facing dialogue.

Default execution model:

- `1 task = 1 active agent session`
- tasks are durable
- execution sessions are lineage
- execution runs are disposable historical attempts
- `SessionBinding` is the current active lease/binding projection, not a permanent 1:1 identity map

Target-state note:

- `ExecutionMode = undecided / lightweight / managed` is an accepted design direction
- it is not yet a stable protocol object

Important subsystems:

- scheduler
- assignment and claim
- session manager
- run manager
- summary manager
- reconcile loop

Related docs:

- [Blackboard](./blackboard.md)
- [Sessions and Runs](./sessions-and-runs.md)
- [Executors](./executors.md)
