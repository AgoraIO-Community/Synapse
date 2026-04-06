# Blackboard

The Shared Blackboard is the only shared fact layer between Communication Brain and Execution Brain.

It should be strongly structured.

Recommended model:

1. append-only mutation and command history
2. materialized current views

Primary object groups:

- tasks
- task mutations
- task commands
- execution sessions
- execution runs
- session bindings
- task summaries
- notification candidates
- interruption state
- target-state execution-mode facts when that layer is stabilized

Core responsibilities:

- shared truth
- revision tracking
- lease and claim visibility
- subscription and notify
- stable query surface for both brains
- fact-first projections that can later be rendered into natural language

It should not become:

- a large natural-language scratchpad
- a place to hide executor-specific internals

Related docs:

- [../protocol/task.md](../protocol/task.md)
- [../protocol/mutation-and-command.md](../protocol/mutation-and-command.md)
- [../protocol/execution-session-and-run.md](../protocol/execution-session-and-run.md)
- [../protocol/summary-notification.md](../protocol/summary-notification.md)
