# RFC 0002: Execution Sessions, Runs, and Agent Management

This RFC preserves the original long-form execution-lineage proposal.

Its content has been absorbed primarily into:

- `docs/architecture/sessions-and-runs.md`
- `docs/architecture/executors.md`
- `docs/protocol/execution-session-and-run.md`

When this RFC conflicts with the stable docs, treat the stable docs as authoritative.

# Detailed Design: Execution Sessions, Runs, and Agent Management

## Context

This design gives Synapse a durable-task, explicit execution-lineage model: keep the work item durable, and make concrete coding-agent attempts disposable, traceable, and executor-aware.

The key lesson is not the kanban UI, Git worktree model, or PR workflow. The key lesson is the separation between:

- the durable thing humans care about
- the executor/session lineage used to get work done

For Synapse, that means:

- keep `Task` as the durable user-visible work item
- add explicit execution lineage below it
- keep agent/session/resume state inside the `Execution Brain`

Synapse should not import kanban-product concepts into the core runtime. The existing Synapse runtime session already serves as the top-level collaboration container.

## Current State

Today, Synapse already has the right high-level architecture split:

- `Communication Brain`
  - owns acknowledgement, clarification, and user-facing response behavior
- `Execution Brain`
  - owns task routing, task lifecycle, executor dispatch, and normalized execution events
- `Shared Blackboard`
  - stores synchronized session state and stream history

The current runtime behavior is still flatter than the target design:

- `Task` is both the durable work item and most of the execution state
- the runtime session is the main collaboration container
- executor routing is base-executor oriented
- executor-specific resume state is not first-class runtime state
- follow-up behavior is task-centric rather than run-centric
- a follow-up against a `done` task currently falls back to creating a new task

That flattening is acceptable for a prototype, but it will become limiting once Synapse supports:

- multiple coding-agent families
- retries with clear lineage
- executor handoffs on the same task
- richer review or follow-up flows
- future delegated or nested task execution

## Design Goals

- Preserve the `Communication Brain` / `Execution Brain` separation.
- Make execution lineage first-class runtime state.
- Keep `Task` durable across retries, follow-ups, and executor handoffs.
- Normalize coding-agent identity and overrides through typed executor configuration.
- Support multiple coding-agent families without leaking backend-specific session details into the rest of the runtime.
- Keep V1 execution policy simple:
  - one active run per task
  - one queued follow-up per task lineage
  - no shared-write parallel execution against the same task
- Keep schemas multi-executor ready even if runtime behavior remains conservative in V1.

## Non-Goals

- No kanban board or issue-management model in Synapse core runtime.
- No Git workspace, worktree, or PR-management abstraction.
- No shared mutable multi-agent editing model for the same task in V1.
- No persistence/database design in this iteration beyond the current in-memory blackboard model.
- No frontend redesign in this iteration beyond exposing richer runtime state in snapshots and stream events.

## Conceptual Model

### `Task`

`Task` remains the durable unit of user-visible work.

It represents:

- the user or system goal
- the current status from the runtime point of view
- durable context and outputs
- parent/child task relationships

It does not represent:

- one specific coding-agent attempt
- one retry
- one follow-up run
- executor-native resume identifiers

### `ExecutionSession`

`ExecutionSession` is the execution-brain-owned lineage for running one task with one base executor family.

It groups related runs that share:

- the same task
- the same base executor family
- optional executor-native resume continuity

An execution session is the Synapse analogue of “stay on the same agent family and continue the work” without turning every follow-up into a new task.

### `ExecutionRun`

`ExecutionRun` is one concrete run inside an execution session.

Examples:

- initial run
- follow-up run
- retry run
- future review run

A run is disposable and historical. It should preserve:

- which executor configuration was used
- what instruction started it
- its progress and final outcome
- what artifacts it produced
- what resume handle it consumed and emitted

### `ExecutorConfig`

`ExecutorConfig` is the normalized executor identity used when dispatching a run.

It captures:

- base executor family
- optional variant
- optional model override
- optional reasoning override
- optional permission/sandbox override

This separates:

- durable executor family identity
- per-run execution overrides

### `AgentResumeHandle`

`AgentResumeHandle` is an opaque execution-brain-level container for executor-native resume state.

It allows follow-up continuity without leaking backend-specific session/message identifiers into:

- `Task`
- Communication Brain logic
- frontend-facing task semantics

### `QueuedRunRequest`

`QueuedRunRequest` stores exactly one follow-up request waiting behind an active run.

This keeps a single queued follow-up request in V1, while remaining intentionally shallow:

- queue depth is `1`
- the newest queued request replaces the older queued request

## Proposed State Model

### New Types

```python
class ExecutorConfig(BaseModel):
    executor_id: str
    variant: str | None = None
    model_id: str | None = None
    reasoning_id: str | None = None
    permission_policy: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
```

```python
class AgentResumeHandle(BaseModel):
    executor_id: str
    session_handle: str | None = None
    turn_handle: str | None = None
    opaque: dict[str, Any] = Field(default_factory=dict)
```

```python
class ExecutionRunReason(StrEnum):
    INITIAL = "initial"
    FOLLOW_UP = "follow_up"
    RETRY = "retry"
    REVIEW = "review"
```

```python
class QueuedRunRequest(BaseModel):
    queued_request_id: str
    task_id: str
    executor_config: ExecutorConfig
    latest_instruction: str
    requested_by_message_id: str | None = None
    created_at: Any = Field(default_factory=utc_now)
    updated_at: Any = Field(default_factory=utc_now)
```

```python
class ExecutionSession(BaseModel):
    execution_session_id: str
    task_id: str
    base_executor_id: str
    run_ids: list[str] = Field(default_factory=list)
    active_run_id: str | None = None
    latest_run_id: str | None = None
    latest_resume_handle: AgentResumeHandle | None = None
    queued_run_request: QueuedRunRequest | None = None
    created_at: Any = Field(default_factory=utc_now)
    updated_at: Any = Field(default_factory=utc_now)
```

```python
class ExecutionRun(BaseModel):
    run_id: str
    execution_session_id: str
    task_id: str
    executor_config: ExecutorConfig
    run_reason: ExecutionRunReason
    status: TaskStatus = TaskStatus.QUEUED
    created_from_message_id: str | None = None
    resume_handle_in: AgentResumeHandle | None = None
    resume_handle_out: AgentResumeHandle | None = None
    latest_progress_message: str | None = None
    progress_percent: float | None = None
    output_summary: str | None = None
    artifacts: list[Artifact] = Field(default_factory=list)
    block_reason: str | None = None
    failure_reason: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: Any = Field(default_factory=utc_now)
    started_at: Any | None = None
    completed_at: Any | None = None
    updated_at: Any = Field(default_factory=utc_now)
```

### `Task` Changes

`Task` should remain the durable work item and gain:

- `created_from_run_id: str | None = None`

`Task` should keep:

- `assigned_executor`
- `candidate_executors`
- `status`
- `artifacts`
- `output_summary`

But `assigned_executor` should remain the base executor family only. It should not become a full executor profile/config object.

### Blackboard State Changes

`BlackboardSessionState` should gain:

- `execution_sessions: dict[str, ExecutionSession]`
- `execution_runs: dict[str, ExecutionRun]`

This keeps:

- task state durable and queryable
- run lineage explicit
- executor-native continuity isolated inside execution state

## State Ownership

### Communication Brain

Communication Brain continues to own:

- acknowledgement
- clarification
- progress phrasing for users
- terminal completion language
- conversational continuity

Communication Brain should not own:

- agent-native session ids
- retry lineage
- run queueing logic
- executor handoff policy

### Execution Brain

Execution Brain owns:

- execution session creation
- run creation
- run dispatch
- queued follow-up behavior
- retry behavior
- executor handoff behavior
- executor-native resume handle storage
- normalization of execution events back into runtime state

### Shared Blackboard

Shared Blackboard stores:

- durable tasks
- execution sessions
- execution runs
- message history
- stream events
- strategy and conversation state

## Protocol Changes

## Task Protocol

Add:

- `created_from_run_id` to `Task`

Keep:

- `TaskStatus` execution-oriented in V1:
  - `queued`
  - `running`
  - `blocked`
  - `canceled`
  - `failed`
  - `done`

Synapse should not mix planning-board state into `TaskStatus`. If a planning/status-board layer is added later, it should use a separate planning-status concept.

## Execution Protocol

Add:

- `ExecutorConfig`
- `AgentResumeHandle`
- `ExecutionRunReason`
- `execution_session_id`
- `run_id`

Extend `ExecutionRequest` so it becomes run-aware:

```python
class ExecutionRequest(BaseModel):
    request_id: str
    session_id: str
    execution_session_id: str
    run_id: str
    task_id: str
    executor_id: str
    executor_config: ExecutorConfig
    request_type: ExecutionRequestType
    task_snapshot: Task
    run_reason: ExecutionRunReason
    resume_handle_in: AgentResumeHandle | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
```

Extend `ExecutionEvent` with:

- `execution_session_id`
- `run_id`
- `resume_handle_out`

## Stream / Snapshot Protocol

`SessionSnapshot` should include:

- `execution_sessions: list[ExecutionSession]`
- `execution_runs: list[ExecutionRun]`

`StreamEvent` should include:

- `related_execution_session_id: str | None = None`
- `related_run_id: str | None = None`

Useful new stream event types:

- `execution_session_created`
- `execution_run_created`
- `execution_run_started`
- `execution_run_progress`
- `execution_run_blocked`
- `execution_run_completed`
- `execution_run_failed`
- `execution_run_canceled`
- `queued_run_request_stored`
- `queued_run_request_replaced`
- `queued_run_request_dispatched`

## Executor Capabilities

Extend `ExecutorCapability` with:

- `supports_resume: bool = False`
- `supports_follow_up: bool = False`
- `supports_setup: bool = False`

Keep:

- `supports_cancel`
- `supports_streaming`
- `capability_tags`

## Runtime Flows

### Create Task

When the router emits `CREATE_TASK`:

1. Build one `Task`.
2. Select the base executor family using the existing router.
3. Build `ExecutorConfig` from:
   - payload override if provided
   - otherwise the selected executor family
4. Create one `ExecutionSession` for the task.
5. Create one initial `ExecutionRun`.
6. Set:
   - task status to `queued`
   - `task.assigned_executor` to the base executor family
   - `execution_session.active_run_id` to the new run
7. Dispatch the run through the selected executor adapter.

### Update / Continue Task

When the router emits `UPDATE_TASK`:

1. Resolve the target task.
2. If unresolved, emit clarification.
3. Determine executor configuration:
   - explicit action payload wins
   - otherwise reuse the latest execution session for the task
   - otherwise fall back to current task/router defaults
4. If the chosen base executor family matches the latest execution session:
   - reuse that session
5. If it differs:
   - create a new execution session for the same task
   - update `task.assigned_executor`
6. If an active run already exists:
   - do not run in parallel
   - replace the single queued follow-up request
7. If no active run exists:
   - create a new `follow_up` run and dispatch it

### Follow-Up Against a `done` Task

This is a deliberate behavior change from the current runtime.

Today:

- follow-up against `done` creates a new task

Target behavior:

- reopen the same task
- create a new run under the same task lineage
- preserve task identity

This matches the design principle that the task is durable and runs are disposable.

### Blocked Task

When a task is blocked and a clarifying follow-up arrives:

- create a new `follow_up` run in the same task lineage
- clear the blocked state when the new run is dispatched
- preserve the blocked run as historical evidence of what happened

### Queued Follow-Up

If the user sends new instruction while a run is active:

- create or replace `queued_run_request`
- queue depth remains `1`
- when the active run finishes or blocks:
  - clear `active_run_id`
  - materialize the queued request into a new run
  - dispatch immediately

### Retry

When the user issues `RETRY_TASK`:

- resolve the task
- choose the latest execution session unless a different executor family is explicitly requested
- create a fresh `retry` run
- do not create a new task
- do not overwrite prior runs

### Cancel

When the user issues `CANCEL_TASK`:

- cancel the active run
- clear queued follow-up state
- preserve all historical execution sessions and runs
- mark the task `canceled` unless an immediate replacement run is intentionally started

### Executor Handoff

If a follow-up or retry switches executor family:

- create a new `ExecutionSession` on the same task
- carry forward task-level context
- do not carry backend-native resume state across executor families
- keep prior execution sessions and runs for auditability

### Review

Reserve `ExecutionRunReason.REVIEW`.

This allows future review-specific agent flows without inventing another top-level runtime object. A review is still:

- about the same task
- part of the same execution lineage
- just a different reason for a run

## Executor Integration Contract

## Codex Execution Implementation

Executor integrations can share a common abstraction plus a Codex-specific implementation.

The practical answer to the Codex question is:

- yes, there is a common abstraction layer in both codebases
- yes, both have a concrete Codex implementation
- yes, both avoid a human-driven interactive TTY workflow
- no, the two Codex implementations are not the same shape

Synapse currently uses a simpler one-shot non-interactive Codex CLI integration, while richer sessionful Codex integrations are possible in principle.

### Sessionful Executor Abstraction Pattern

A richer sessionful executor integration typically has a common stack like:

- `ExecutorAction` and `Executable`
  - unify initial runs, follow-ups, reviews, and scripts
- `StandardCodingAgentExecutor`
  - defines the common coding-agent interface
  - includes `spawn`, `spawn_follow_up`, and `spawn_review`
- `ExecutorConfig`
  - normalizes executor family plus per-run overrides
- agent-specific implementations
  - Claude, Codex, Gemini, and others all plug into the same interface

This is architecturally important because Synapse's proposed `ExecutionSession` and `ExecutionRun` split fits this model well: the executor family and overrides are normalized at the common layer, while backend-specific continuity remains isolated in the concrete implementation.

### Sessionful Codex Integration Pattern

A richer Codex implementation is not a plain `codex exec --json` wrapper.

It uses:

- base command:
  - `npx -y @openai/codex@0.116.0 app-server`
- stdio process management
- an app-server client
- JSON-RPC communication
- thread/session start or fork semantics

Important details:

- `spawn` calls into a Codex-specific `spawn_slash_command` path
- `spawn_follow_up` reuses the same common interface but passes a prior session/thread id
- `spawn_review` is also implemented through the same Codex integration
- approval policy, sandbox mode, plan mode, reasoning, and model overrides are all applied through the shared executor config and translated into Codex thread start params
- follow-up behavior is true Codex-native continuity because the implementation starts or forks Codex threads instead of just replaying context into a fresh one-shot process

So from the product/runtime point of view, it is non-interactive, but it is not merely a one-off CLI call. It is a programmatic, sessionful Codex integration.

### Shared Abstraction in Synapse Today

Synapse also already has a common executor abstraction:

- `AsyncExecutor`
  - top-level async executor protocol
- `ExternalAsyncExecutor`
  - shared adapter for external backends
- `ExternalExecutorBackend`
  - backend-specific start/wait/cancel contract
- concrete backend
  - `CodexCliBackend`

The main files are:

- `runtime/executors/base.py`
- `runtime/executors/external.py`
- `runtime/executors/external_backend.py`
- `runtime/executors/codex/backend.py`

This means Synapse already has the right overall structure for multiple executors. The missing piece is not abstraction. The missing piece is richer executor-native session continuity and explicit run lineage above the backend.

### How Codex Works in Synapse Today

Synapse's current Codex backend is intentionally much simpler than a sessionful Codex integration.

It launches:

- `codex exec`
- with `--json`
- with `--ephemeral`
- with `--output-last-message`

The backend then:

- builds one prompt from the task snapshot
- starts a subprocess with `asyncio.create_subprocess_exec`
- reads newline-delimited JSON events from stdout
- normalizes those JSON events into transient or durable `ExecutionEvent`s
- captures the final output from the output file and returns one `ExternalExecutionResult`

This is a non-interactive CLI integration in the straightforward sense: one subprocess, one prompt, one result, plus streamed progress events parsed from JSON stdout.

It is useful because:

- it is simple
- it keeps the transport thin
- it normalizes Codex activity into Synapse execution events

But it does not currently provide true Codex-native follow-up continuity. The current implementation is a disposable run model.

### Design Implications for Synapse

The proposed `Task` / `ExecutionSession` / `ExecutionRun` model works with both styles of executor integration.

For Synapse specifically:

- the current `codex exec --json --ephemeral` backend is a good fit for disposable `ExecutionRun`s
- it is not yet a good fit for executor-native resumable `ExecutionSession`s
- follow-up continuity in Synapse today should be treated as logical runtime continuity, not true Codex thread continuity

That matters for the design:

- `AgentResumeHandle` must remain optional
- `supports_resume` must be capability-driven, not assumed for all executors
- follow-up runs must support a fallback mode where continuity is synthesized from:
  - task goal
  - latest instruction
  - recent summary
  - selected artifacts or task context

If Synapse later wants true Codex-native resume behavior, it will likely need one of two changes:

- a richer Codex app-server or sessionful protocol integration
- a backend-supported resume handle path exposed by the non-interactive Codex interface

Until then, Synapse should explicitly model the difference between:

- runtime-level continuity
- executor-native continuity

That distinction is one of the main reasons this design introduces `ExecutionSession`, `ExecutionRun`, and optional `AgentResumeHandle` instead of assuming every executor can resume natively.

## Backend Request Contract

Extend `ExternalExecutionRequest` with:

- `execution_session_id`
- `run_id`
- `executor_config`
- `run_reason`
- `resume_handle_in`

Extend `ExternalExecutionResult` with:

- `resume_handle_out: AgentResumeHandle | None = None`

## Resume Semantics

If `supports_resume=True`:

- follow-up runs receive `resume_handle_in`
- executor backends are responsible for using that handle correctly
- execution brain persists the returned `resume_handle_out`

If `supports_resume=False`:

- follow-up runs start fresh
- execution brain synthesizes continuity using task context, latest instruction, and recent run summary

This keeps higher-level runtime behavior stable even when executors differ in capability.

## Opaque Handle Rule

Resume handles are opaque above the executor backend boundary.

They must not be interpreted by:

- Communication Brain
- generic routing logic
- task display semantics

They are only carried and stored by Execution Brain.

## Why Synapse Uses a Narrower Runtime Model

Synapse should use the execution-lineage ideas without importing a broader task-board product model.

A broader execution product may separate:

- planning artifacts
- workspaces
- sessions
- execution processes

Synapse should adapt that into:

- runtime session
- task
- execution session
- execution run

Important differences:

- Synapse runtime session is the top-level container
- Synapse core runtime has no issue/kanban model
- Synapse core runtime has no Git workspace/worktree abstraction
- Synapse V1 should not support shared-write parallel runs on the same task

This is intentionally narrower and cleaner for a protocol-first runtime.

## Testing / Acceptance Criteria

### Functional Acceptance

- A task survives multiple follow-ups without turning into duplicate tasks.
- A `done` task can be reopened by creating a new run on the same task.
- Retry creates a new run, not a new task.
- Switching coding-agent family creates a new execution session under the same task.
- A busy task stores exactly one queued follow-up.
- Queued follow-up dispatches automatically when the active run ends.

### Snapshot / Streaming Acceptance

- Session snapshots expose tasks, execution sessions, and execution runs together.
- Stream events can be correlated back to task, execution session, and run.
- Frontend or operators can inspect current run plus previous attempts without reconstructing hidden lineage.

### Executor Acceptance

- Resume-capable executors receive resume handles on follow-up.
- Non-resume-capable executors still support follow-up through synthesized context.
- Executor-native session details do not leak into Communication Brain logic.

## Open Questions Deferred

- How execution sessions and runs should persist beyond the current in-memory runtime
- Whether future review UX needs dedicated frontend panels
- Whether queued follow-up depth should remain `1` long-term
- Whether future delegated sub-runs should become a separate child-run model or remain child tasks
- Whether setup/helper behavior should become explicit run reasons in Synapse, similar to richer executor orchestration systems

## Implementation Impact

This design would primarily affect:

- `runtime/protocols/tasks.py`
- `runtime/protocols/execution.py`
- `runtime/protocols/stream.py`
- `runtime/shared_blackboard/blackboard_state.py`
- `runtime/shared_blackboard/runtime_state.py`
- `runtime/execution_brain/orchestrator.py`
- `runtime/execution_brain/task_graph.py`
- `runtime/executors/base.py`
- `runtime/executors/external_backend.py`
- `runtime/executors/external.py`

It should also lead to targeted updates in integration and protocol tests so the runtime asserts:

- durable task identity
- explicit run lineage
- queueing behavior
- executor handoff semantics

## Default Assumptions

- Runtime scope remains backend-first.
- V1 allows one active run per task.
- V1 allows one queued follow-up per task lineage.
- `TaskStatus` remains execution-oriented in V1.
- `assigned_executor` remains a base executor-family field.
- `ExecutorConfig` is the only typed place for per-run executor overrides.
- `ExecutionSession` groups runs by task plus base executor family.
- `REVIEW` is reserved now to avoid a future schema break.
