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
- `ExecutionRun.latest_progress_message` is the normalized current
  user-facing progress text; adapters may derive it from executor-native
  streams such as ACPX output chunks or Codex commentary deltas

Detached-executor additions:

- `ExecutionSession.executor_node_id`
  - identifies which detached executor node currently owns the live real-executor lineage
- `ExecutionSession.continuity_key`
  - optionally groups multiple tasks into one reusable executor-side lineage when
    they belong to the same Bro detail generation
- `SessionBinding.executor_node_id`
  - records which node the current binding is associated with
- `TaskStatus = waiting_executor`
  - task is accepted and durable state exists, but Synapse is waiting for the
    detached executor node to become available
- `RunStatus = waiting_executor`
  - the current run has been created but is waiting on detached-host availability

Workspace rule:

- `session_affinity` is an opaque workspace id, not a control-plane filesystem
  path
- the detached executor node maps that id to a node-local working directory

Bro detail continuity:

- draft-created tasks assigned to the same Bro detail generation reuse the same
  executor session when executor family and `executor_node_id` also match
- rebinding a Bro to a different executor node rotates the Bro detail generation,
  so future tasks create a new execution session
- old tasks remain durable history; clients filter recent Bro detail tasks by
  the current generation id
