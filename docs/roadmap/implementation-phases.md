# Implementation Phases

This document is the canonical phased implementation roadmap for Synopse.

The build order is deliberately separated from the final architecture description.

## Phase 0: Docs + Scaffold

### Goal

Freeze the package layout, tooling, and contributor-facing repository skeleton before major feature migration begins.

### What Gets Built

- `src/synopse/` target layout is fixed in docs
- package skeletons are created
- top-level repo structure is fixed:
  - `tests/`
  - `evals/`
  - `fixtures/`
  - `replays/`
  - `scripts/`
  - `examples/`
- docs explain the intended module boundaries
- testing and eval directory structure is defined

### What Does Not Get Built Yet

- full runtime migration
- real executor integration
- blackboard persistence beyond minimal scaffolding

### Validation Focus

- repo structure clarity
- packaging clarity
- contributor onboarding clarity

### Exit Criteria

- target package structure is documented and unambiguous
- docs and `AGENTS.md` agree on the structure
- roadmap and verification docs exist
- contributors can tell where any new code should go without guessing

## Phase 1: Protocol + Blackboard Core

### Goal

Make the protocol and in-memory blackboard the first stable executable core.

### What Gets Built

- protocol models:
  - `Task`
  - `TaskMutation`
  - `TaskCommand`
  - `ExecutionSession`
  - `ExecutionRun`
  - `SessionBinding`
  - `TaskSummary`
  - `NotificationCandidate`
  - `Interruption`
- shared enums
- in-memory blackboard backend
- query and revision primitives
- claim and lease primitives:
  - `task_revision`
  - `execution_revision`
  - `claimed_by`
  - `claim_expires_at`

### What Does Not Get Built Yet

- real executor scheduling
- communication brain tool orchestration
- proactive notifications

### Validation Focus

- schema correctness
- blackboard CRUD and query behavior
- revision and lease semantics

### Exit Criteria

- protocol churn is low
- blackboard supports the core domain objects
- deterministic protocol and blackboard tests pass

## Phase 2: Execution Brain Minimal Loop

### Goal

Run tasks from blackboard state using a fake executor and explicit session/run objects.

### What Gets Built

- execution brain loop
- scheduler
- assignment manager
- run manager
- session manager
- fake executor adapter
- basic summary refresh
- executor core abstractions

### What Does Not Get Built Yet

- rich communication behavior
- proactive notification delivery
- real external executor adapter

### Validation Focus

- claim/assign/run/block/complete flow
- session reuse policy
- deterministic state transitions

### Exit Criteria

- execution brain can drive tasks end-to-end with a fake executor
- runs and sessions are visible in blackboard state
- blocked and completed states produce expected summaries
- execution state transitions are deterministic under fake execution

## Phase 3: Communication Brain Minimal Loop

### Goal

Make Communication Brain able to manipulate and query blackboard through tools, with natural replies.

### What Gets Built

- communication brain
- create/update/control/query tools
- task reference resolution
- action-commitment reply policy
- fake/scripted communication model harness

### What Does Not Get Built Yet

- full dual-brain closed loop
- notification orchestration
- real executor-native continuity

### Validation Focus

- tool choice correctness
- task manipulation correctness
- non-mechanical user-facing replies

### Exit Criteria

- communication brain can reliably create/update/control/query
- replies do not degrade into system acknowledgements
- task reference resolution is minimally usable
- deterministic tests can exercise the brain with a fake/scripted model

## Phase 4: Dual-Brain Closed Loop

### Goal

Connect communication and execution through the blackboard as the only shared source of truth.

### What Gets Built

- communication writes become execution inputs
- execution updates become summary/queryable outputs
- blocked -> user input -> resume flow
- cancel/retry/reopen behavior
- session reuse through the blackboard as the only shared state

### What Does Not Get Built Yet

- mature notification system
- real adapter production hardening

### Validation Focus

- end-to-end correctness with fake components
- no hidden coupling between communication and execution internals
- task identity stability across runs

### Exit Criteria

- full dual-brain loop works with fake executor and fake/scripted communication
- task/session/run state is coherent end-to-end
- communication does not depend on execution internals directly

## Phase 5: Notifications, Interruptions, Real Adapter

### Goal

Add proactive communication, interruption orchestration, and at least one real executor adapter.

### What Gets Built

- notification queue and candidate model
- aggregation and digest delivery
- interruption manager
- one real executor adapter, likely Codex first

### What Does Not Get Built Yet

- multiple production-grade adapters
- broad multi-backend persistence optimization

### Validation Focus

- notification quality
- interruption correctness
- real adapter contract behavior

### Exit Criteria

- proactive communication is coherent and not noisy
- interruption rules behave correctly
- one real adapter passes contract and smoke checks
- real adapter assumptions remain aligned with the documented executor contract
