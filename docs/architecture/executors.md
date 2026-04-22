# Executors

Synapse should expose a clean separation between:

- executor core abstractions
- concrete executor adapters

Stable core concepts:

- `Executor`
- `ExecutorSession`
- `ExecutorEvent`
- `ExecutorResult`
- `ExecutorCapabilities`
- `Executor Host`

Important capability directions:

- `supports_resume`
- `supports_follow_up`
- `supports_setup`

Current deployment direction:

- `mock` remains an in-process adapter
- real executors such as `codex` and `acpx` run inside the detached executor
  host
- the main Synapse API process registers hosted executor proxies rather than
  launching real executor subprocesses directly

Executor-host note:

- the detached host owns live executor-native session continuity
- Synapse keeps durable execution lineage and user-facing control semantics
- executor-native continuity still remains optional across executor families
- detached executor hosts connect to the main Synapse service origin through
  `WS /executors/control`
- foreground `synapse executor run` output should make connect, ready,
  disconnect, and retry state explicit, and should only report ready after the
  control-channel registration handshake succeeds

Adapter direction:

- Codex is one real adapter family
- OpenClaw or other executor families should fit behind the same normalized executor contract

This is why:

- `AgentResumeHandle` must stay optional
- runtime continuity and executor-native continuity must remain distinct concepts
- `session_affinity` should be treated as an opaque workspace id that the
  detached host resolves into a host-local directory

Related docs:

- [../protocol/execution-session-and-run.md](../protocol/execution-session-and-run.md)
- [Sessions and Runs](./sessions-and-runs.md)
