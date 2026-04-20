# RFC 0008: Execution Detail Context And System-Prompt Audit

## Summary

This RFC adds two backend-only capabilities to Synapse:

1. a structured task execution-detail log that lets `Communication Brain` see how far recent tasks have progressed
2. an always-on diagnostic view of the exact `system` messages sent on `Communication Brain` message turns

The goal is to let `Communication Brain` answer progress questions with materially better grounding while also making it easy to audit the effective system prompt used for a given request.

## Problem

Today the runtime exposes progress to `Communication Brain` mainly through:

- `TaskSummary`
- `ExecutionRun.latest_progress_message`
- explicit tool reads such as `query_task_detail`

That is enough for shallow progress replies, but not enough to reliably answer questions about how far a task has progressed. The current state projection collapses a run into a latest status-oriented view rather than a recent execution history.

Separately, the observability stack can already record full built LLM requests when verbose logging is enabled, but there is no always-on audit field dedicated to the exact `system` messages that form the effective prompt prefix for `Communication Brain`.

## Goals

- store structured execution detail history per task
- keep that history on the blackboard rather than hidden in executor-specific internals
- make recent execution detail available to `Communication Brain` as part of normal prompt context
- restrict automatic context injection to the last 5 tasks with recent execution-detail activity
- cap injected execution-detail history to the last 20 entries per included task
- add always-on diagnostics for the exact `system` messages sent on `Communication Brain` message turns
- keep the first implementation backend-only

## Non-Goals

- no frontend or websocket contract changes in v1
- no `SessionSnapshot` changes in v1
- no raw executor transcript dumping into blackboard
- no unified timeline that mixes mutations, commands, and execution into one auto-injected prompt surface
- no focused-task exception to the “last 5 tasks” rule

## Design Principles

- keep `Communication Brain` and `Execution Brain` separate
- keep transport thin
- treat protocol models as the source of truth
- keep the blackboard structured rather than turning it into a natural-language scratchpad
- preserve multi-executor compatibility even though runtime v1 is single-executor

## Proposed Data Model

Add a new protocol object:

### `TaskExecutionDetailEntry`

- `detail_id: str`
- `task_id: str`
- `run_id: str`
- `execution_session_id: str`
- `event_type: str`
- `text: str`
- `created_at: str`
- `payload: dict[str, object]`

### Semantics

- each entry belongs to one task
- each entry is also anchored to the originating run and execution session
- entries are append-only
- `text` is the normalized human-readable detail used for prompts and debugging
- `payload` holds structured extra fields needed for debugging or future projections

This object is execution-only. It does not replace:

- `TaskSummary`
- `ExecutionRun`
- `TaskMutation`
- `TaskCommand`

## Blackboard Changes

Extend `BlackboardStore` with:

- `append_task_execution_detail(entry)`
- `list_task_execution_details(task_id, limit: int | None = None)`
- `list_recent_task_execution_details(task_limit: int = 5, entry_limit: int = 20)`

### Query Rules

- `list_task_execution_details(task_id, limit)` returns entries for one task in append order
- when `limit` is provided, it means “most recent N entries,” still returned oldest-to-newest
- `list_recent_task_execution_details(task_limit, entry_limit)` selects the tasks with the most recent execution-detail activity and returns bounded per-task detail history for those tasks

Storage remains append-only. Bounded behavior is applied only to reads used for context and query convenience.

## Execution Write Path

`Execution Brain` owns execution detail generation.

`RunManager.apply_event` should append one `TaskExecutionDetailEntry` for each executor event:

- `progress`
- `blocked`
- `completed`
- `failed`
- `cancelled`

The entry text should be normalized from the executor event message. The runtime must not store raw executor-native transcripts or unbounded log streams as prompt context.

Existing projections remain unchanged:

- `ExecutionRun.latest_progress_message` still tracks the latest progress line
- `TaskSummary` still provides the concise user-facing projection

The detail log is additive rather than a replacement.

## Communication Brain Context Policy

`Communication Brain` should receive execution-detail context automatically, but only within strict limits.

### Selection

- select the 5 tasks with the most recent execution-detail activity
- do not include older tasks just because they are focused
- if a user asks about an older task, the model should use `query_task_detail`

### Per-Task Bound

- include only the last 20 execution-detail entries per selected task
- preserve chronological order from oldest to newest within the bounded slice

### Scope

- auto-inject execution details only
- do not auto-inject mutations or commands for this feature
- keep mutation and command histories available through their existing stores and query paths

## Tooling Changes

Extend `query_task_detail` with:

- optional `limit`, default `20`

Return:

- existing task, binding, summary, runs, sessions, mutations
- existing commands
- new `execution_detail_entries`

This gives the model and developers a direct way to inspect older tasks or deeper history without expanding auto-context for every turn.

## Observability Changes

Keep `comm.llm.request_built` as the main message-turn LLM request event.

Add an always-on field:

- `details.system_messages`

### Rules

- `system_messages` must contain the exact built `role == "system"` message objects in send order
- this field is always present for `Communication Brain` message-turn request traces
- full built `messages` remain gated behind `SYNAPSE_LOG_LLM_DETAILS=true`
- notification traces keep their current behavior in v1 unless explicitly expanded later

This yields a narrow, auditable prompt view without forcing full verbose LLM logging on every run.

## Risks And Tradeoffs

### Prompt Growth

Including execution detail for multiple tasks increases prompt size. The `5 tasks x 20 entries` bound is the control mechanism for v1.

### Blackboard Bloat

Append-only execution detail can grow over time. That is acceptable for v1 because storage is in-memory and bounded reads are used for prompts. If durable storage is added later, retention policy may need a separate design.

### Dual Debug Surfaces

There is now a distinction between:

- always-on `system_messages`
- verbose full `messages`

This is intentional. The narrow audit view is for prompt verification; the full request payload remains an opt-in debugging surface.

## Rollout

1. add the RFC
2. implement protocol and blackboard support
3. wire execution writes and Communication Brain context reads
4. add system-message audit logging
5. add tests
6. after adoption, merge the stable contract into `docs/protocol/`, `docs/architecture/`, and `docs/memories.md`

## Acceptance Criteria

- execution events append structured task execution-detail entries
- `Communication Brain` sees execution details for only the last 5 detail-active tasks
- each included task contributes at most 20 execution-detail entries
- older focused tasks are not auto-included
- `query_task_detail(limit=...)` returns bounded execution-detail entries
- `comm.llm.request_built` always includes exact `system_messages` for message turns
- full built request messages remain gated behind `SYNAPSE_LOG_LLM_DETAILS`
