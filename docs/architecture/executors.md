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

- when enabled, Synopse can register a real Codex app-server executor beside the mock adapter
- Codex follow-ups should reuse durable runtime session lineage plus executor-native thread handles when available
- executor-native continuity still remains optional across executor families

Adapter direction:

- Codex is one real adapter family
- OpenClaw or other executor families should fit behind the same normalized executor contract

This is why:

- `AgentResumeHandle` must stay optional
- runtime continuity and executor-native continuity must remain distinct concepts

Related docs:

- [../protocol/execution-session-and-run.md](../protocol/execution-session-and-run.md)
- [Sessions and Runs](./sessions-and-runs.md)
