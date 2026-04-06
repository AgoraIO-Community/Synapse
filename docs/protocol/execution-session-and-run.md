# Execution Session and Run Protocol

Key objects:

- `ExecutorConfig`
- `AgentResumeHandle`
- `QueuedRunRequest`
- `ExecutionSession`
- `ExecutionRun`
- `SessionBinding`
- `TaskExecutionMode`
- `ExecutionState`

Responsibilities:

- `ExecutorConfig`
  - normalized executor identity and per-run override
- `AgentResumeHandle`
  - opaque executor-native continuity handle
- `QueuedRunRequest`
  - one queued follow-up request for an active lineage
- `ExecutionSession`
  - lineage for a task under one executor family
- `ExecutionRun`
  - one concrete run inside that lineage
- `SessionBinding`
  - current active lease/binding projection
- `TaskExecutionMode`
  - current task-level execution classification projection
- `ExecutionState`
  - current runtime snapshot

Relationship note:

- task identity is durable
- session identity is executor-side lineage
- run identity is disposable
- binding is phase-based rather than permanent

Core rule:

- task identity is durable
- run identity is disposable
