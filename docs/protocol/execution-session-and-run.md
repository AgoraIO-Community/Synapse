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

Detached-executor additions:

- `ExecutionSession.executor_host_id`
  - identifies which detached executor host currently owns the live real-executor lineage
- `SessionBinding.executor_host_id`
  - records which host the current binding is associated with
- `TaskStatus = waiting_executor`
  - task is accepted and durable state exists, but Synapse is waiting for the
    detached executor host to become available
- `RunStatus = waiting_executor`
  - the current run has been created but is waiting on detached-host availability

Workspace rule:

- `session_affinity` is an opaque workspace id, not a control-plane filesystem
  path
- the detached executor host maps that id to a host-local working directory
