# Verification Strategy

This document separates deterministic testing from quality-oriented evaluation.

Core rule:

- `tests/` verify correctness
- `evals/` verify behavior quality

A second rule is:

- verify protocol first
- verify runtime behavior second
- verify interaction quality third

## Unit Tests

### Purpose

Verify deterministic logic in isolation.

### What Belongs Here

- protocol validation
- blackboard logic
- scheduler scoring
- assignment policy
- session reuse policy
- interruption resolution
- notification aggregation rules

### CI Expectation

- always run
- fast
- deterministic

## Integration Tests

### Purpose

Verify subsystem interaction under controlled conditions.

### What Belongs Here

- communication + blackboard
- execution + blackboard
- notification pipeline
- interruption flow

### CI Expectation

- standard CI
- deterministic
- may use fake executor and scripted communication model

## E2E Tests

### Purpose

Verify system flow with fake components and realistic orchestration.

### What Belongs Here

- create task and execute
- interrupt running task
- proactive digest flow
- session reuse

### CI Expectation

- may be slower
- still deterministic where possible

## Evals

### Purpose

Verify quality of behavior and interaction rather than strict deterministic correctness.

### What Belongs Here

- whether replies sound mechanical
- whether tools are used appropriately
- whether proactive notifications are too noisy
- whether interruption handling feels natural

### CI Expectation

- not required in the fast path
- may run manually, in extended CI, or nightly

## Shared Fixtures

Recommended shared material:

- `fixtures/blackboard/`
- `fixtures/conversations/`
- `fixtures/executors/`
- `fixtures/scenarios/`

Use these for both tests and evals when possible.

## Fake Components

Two fake components are recommended early:

- scripted fake executor
- fake or scripted communication model / tool harness

These keep early phases testable without depending on external systems.

## Recommended Repository Separation

```text
tests/
├─ unit/
├─ integration/
└─ e2e/

evals/
├─ communication/
├─ execution/
├─ notification/
├─ interruption/
├─ scenarios/
└─ run.py

fixtures/
├─ blackboard/
├─ conversations/
├─ executors/
└─ scenarios/

replays/
```

Interpretation:

- `tests/`
  - deterministic correctness
- `evals/`
  - quality and interaction behavior
- `fixtures/`
  - reusable scenario inputs
- `replays/`
  - optional captured traces for replay-based validation

## CI Layers

### Fast CI

- lint
- unit tests

### Standard CI

- unit tests
- integration tests

### Extended Validation

- e2e tests
- evals

### Real Adapter Validation

- smoke tests
- nightly or manual workflows
- not required for every normal CI run

## Phase Alignment

The preferred implementation order and verification order should move in parallel:

- Phase 0
  - validate structure and docs
- Phase 1
  - validate protocol and blackboard
- Phase 2
  - validate execution with fake executor
- Phase 3
  - validate communication with fake/scripted model
- Phase 4
  - validate closed-loop behavior
- Phase 5
  - validate notifications, interruptions, and one real adapter
