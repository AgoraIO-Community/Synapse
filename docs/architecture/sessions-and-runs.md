# Sessions and Runs

Synopse `v2` separates durable work items from execution lineage.

Core concepts:

- `Task`
  - durable logical work item
- `ExecutionSession`
  - executor-family-specific lineage for a task
- `ExecutionRun`
  - one concrete execution attempt within a session
- `SessionBinding`
  - current live binding and lease projection

Default policy:

- one active task owns one active session
- task follow-ups reuse the current session when possible
- retries append new runs
- completed tasks can be reopened without creating duplicate tasks
- executor-family handoff creates a new execution session under the same task

This model is what lets Synopse preserve:

- stable user-facing task identity
- clear execution history
- future executor-native continuity when supported

Related docs:

- [../protocol/execution-session-and-run.md](../protocol/execution-session-and-run.md)
- [Executors](./executors.md)
