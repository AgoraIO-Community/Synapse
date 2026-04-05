# Executors

Synopse should expose a clean separation between:

- executor core abstractions
- concrete executor adapters

Stable core concepts:

- `Executor`
- `ExecutorSession`
- `ExecutorEvent`
- `ExecutorResult`
- `ExecutorCapabilities`

Important capability directions:

- `supports_resume`
- `supports_follow_up`
- `supports_setup`

Codex note:

- the current Synopse Codex integration is closer to a one-shot non-interactive run
- it should be treated as a disposable `ExecutionRun`
- true executor-native continuity must remain optional

This is why:

- `AgentResumeHandle` must stay optional
- runtime continuity and executor-native continuity must remain distinct concepts

Related docs:

- [../protocol/execution-session-and-run.md](../protocol/execution-session-and-run.md)
- [Sessions and Runs](./sessions-and-runs.md)
