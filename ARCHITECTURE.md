# Newbro Architecture

Newbro is a backend-first runtime built around a dual-brain model:

- `Communication Brain`
- `Execution Brain`
- `Blackboard`

The design goal is not a single-threaded assistant that thinks, talks, and executes in one loop. The goal is a system where conversation and execution are decoupled, long-running work does not make the assistant disappear, and execution state can flow back to the user in a natural voice.

## Status

- This document is the stable architecture target for Newbro `v2`.
- Detailed subsystem and protocol references remain under `docs/architecture/`, `docs/protocol/`, and `docs/roadmap/`.
- `ExecutionMode = undecided / lightweight / managed` is now treated as a stable execution projection, while richer mode-dependent behavior remains implementation work for later phases.

## Terminology

- `Task` is the durable logical work item.
- `ExecutionSession` is executor-side lineage or runtime context for a task.
- `ExecutionRun` is one concrete execution attempt inside a session.
- `SessionBinding` is the current lease or active binding projection between a task and an execution session.
- `Executor Host` is the detached worker process that owns live real-executor sessions and connects back to Newbro over the executor-control websocket.
- `list_tasks` in this document means the Communication Brain's task-retrieval and disambiguation tool. It does not mean "dump every stored task without intent."

## Design Goal

Newbro should let users interact with the system as if they were talking to a person who can both converse and work:

- users can hand off tasks conversationally
- the assistant can acknowledge, clarify, and continue talking while work happens asynchronously
- long tasks remain visible through summaries, notifications, and natural follow-up replies
- the runtime can sit above different executors such as Codex, OpenClaw, or other adapters

## Core Runtime

The runtime is organized around three actors:

### Communication Brain

Communication Brain owns user-facing interaction:

- understanding the current user turn
- choosing whether to call tools
- creating, updating, controlling, and querying tasks through tools
- generating natural user-facing replies
- turning stable blackboard facts into conversational language

It should not:

- manage executor sessions directly
- own scheduling or claim logic
- depend on raw executor-native state

There is no standalone message interpreter in the primary `v2` design. Interpretation lives inside Communication Brain tool use.

### Execution Brain

Execution Brain owns execution runtime behavior:

- discovering runnable tasks
- claim and lease management
- session lifecycle
- executor dispatch
- status and result projection
- summary maintenance
- interruption handling on the execution side
- host-availability handling for detached real executors

It should not:

- talk directly to the user
- generate final user-facing dialogue
- depend on Communication Brain prompts or internal phrasing logic

### Blackboard

Blackboard is the only shared fact source between the two brains.

Communication Brain and Execution Brain do not coordinate through hidden calls or shared in-memory private state. They coordinate by reading and writing blackboard objects.

Observability is a supporting subsystem layered across those actors.
It does not replace blackboard state or websocket debugger streams; it adds
incident-oriented correlation, reason codes, and diagnostic timelines.

## Communication Brain

Communication Brain should use a small, semantically clear tool surface:

- `create_task`
- `update_task`
- `control_task`
- `add_task_note`
- `add_constraint`
- `list_tasks`
- `query_task_summary`
- `query_task_detail`

The outward reply policy is strict:

- internal tool success is not user-facing text
- replies should sound like action commitment, not system acknowledgement
- internal runtime vocabulary should stay hidden unless the user explicitly asks
- spoken replies should feel like a person taking ownership of work

Examples of good outward style:

- "Okay, I'll look into that."
- "Got it, I'll handle that first."
- "I'll keep that on hold for now."
- "I'll check and tell you what I find."

Not:

- "task created successfully"
- "task updated successfully"
- "command applied"

Task-first routing is the default.

- only clear social, subjective, or Newbro-meta conversation should remain pure chat
- actionable requests should usually become tasks, even when phrased as questions
- capability-gated requests such as checking machine state, reading the current workspace, or running commands are one important subset of those task requests
- when only a mock executor is available, ordinary task requests should be blocked by default unless they are explicitly mock-safe

## Execution Brain

Execution Brain runs on task/session/run objects, not on user utterances.

Its core objects are:

- `Task`
- `ExecutionSession`
- `ExecutionRun`
- `SessionBinding`
- `TaskSummary`

It is responsible for:

- task discovery
- assignment and lease policy
- session reuse
- run creation
- summary refresh
- choosing how execution should continue after updates or interruptions

### Execution Classification

`ExecutionMode = undecided / lightweight / managed` is a stable execution projection.

The first-version classification rule is:

- tasks begin as `undecided`
- terminal tasks below the elapsed-time threshold become `lightweight`
- tasks at or above the elapsed-time threshold become `managed`
- mode transitions only upgrade; they do not automatically downgrade

The important boundary is that executors provide execution signals, while Execution Brain owns classification decisions and writes the resulting projection back to blackboard-facing state.

Real executors now run outside the main Newbro API process.

- the control plane keeps durable `Task`, `ExecutionSession`, `ExecutionRun`, and `SessionBinding` state
- a detached `Executor Host` owns live Codex and ACPX runtime sessions
- the control plane talks to that host through a dedicated executor-control websocket
- `mock` remains in-process for mock-safe flows and deterministic tests

## Observability

Newbro should instrument boundary crossings and runtime decisions with one
canonical diagnostic event schema.

The first version keeps observability diagnosis-focused:

- emit structured JSON logs to stdout
- keep a per-session in-memory diagnostic event timeline for drill-downs
- preserve existing websocket `tool_call` / `llm_trace` events as debugger-only transport surfaces

The observability layer should center correlation ids and reason codes rather
than unstructured string logging.

## Blackboard

Blackboard is the fact layer and the only source of truth.

It should at least carry:

- `Task`
- `TaskMutation`
- `TaskCommand`
- `ExecutionSession`
- `ExecutionRun`
- `SessionBinding`
- `TaskSummary`
- `NotificationCandidate`
- `TaskExecutionMode`
- interruption-related state

Its role is to record:

- what tasks exist
- what changed about those tasks
- which tasks are claimed
- which sessions are bound
- what summaries and results are currently visible
- which changes are worth notifying to the user

It must remain strongly structured. It should not become a natural-language scratchpad or a place to hide executor-specific internals.

## Task, Session, And Run

`Task` and `ExecutionSession` are not conceptually the same thing.

- `Task` is the durable logical work item
- `ExecutionSession` is executor-side runtime context
- `ExecutionRun` is one execution attempt inside that context
- `SessionBinding` captures the current active association

The relationship is phase-based, not permanently one-to-one.

The first-version default policy is:

- one session runs one active task at a time
- multi-task concurrency is achieved with multiple sessions
- session reuse is decided by Execution Brain
- task identity remains stable even when sessions or runs change

## Summary, Notification, And Interruption

### Summary

Summary should be maintained by Execution Brain because it has the clearest visibility into:

- current execution state
- blocking reasons
- whether user input is needed
- latest progress and results

Summary should have two layers:

- structured summary facts
- natural-language summary for user-facing replies and notifications

Facts come first. Human-readable language comes later.

### Notification

Notification is not the same thing as blackboard state change.

The intended flow is:

1. Execution Brain updates blackboard.
2. Notification candidates are derived from meaningful state changes.
3. Notification policy decides whether to send, merge, or defer.
4. LLM can turn chosen facts into final natural wording.
5. Only emitted messages enter user-visible conversation history.

The first-version notification defaults should prefer:

- `completed`
- `blocked`
- `needs_input`
- important user-facing result

And should generally avoid:

- routine progress chatter
- claim or session noise
- retry bookkeeping
- silent summary refreshes

### Interruption

Interruption must distinguish stopping speech from stopping work.

Default rule:

- when the user barges in, stop current output first
- do not cancel background work by default
- only explicit task-control or task-update intent should affect execution

This is why interruption belongs partly in Communication Brain and partly in Execution Brain, with blackboard as the coordination layer.

## LLM Boundaries

LLM use should be concentrated at boundary points.

Good uses:

- interpreting the current user turn inside Communication Brain
- choosing tools
- generating natural user-facing replies
- generating natural progress or notification wording from stable facts

Avoid using LLMs for:

- blackboard state updates
- scheduler decisions
- lease and claim logic
- session management
- per-event execution bookkeeping
- notification merge or delivery policy

The principle is simple:

- facts first
- language later

## Repository Structure

Newbro should stay organized by domain boundaries rather than by generic web-backend layers.

Recommended core modules:

- `protocol/`
- `blackboard/`
- `communication/`
- `execution/`
- `executor_core/`
- `executor_adapters/`
- `notification/`
- `runtime/`
- `api/`
- `cli/`

This matches the open-source direction already documented in `docs/architecture/repository-structure.md`.

## Delivery And Validation

Implementation should progress in phases:

1. protocol + blackboard
2. execution + fake executor
3. communication + task tools
4. communication/execution closed loop
5. notification / interruption
6. real executor adapters such as Codex and OpenClaw

Validation should stay split:

- `tests/` for deterministic correctness
- `evals/` for behavioral quality

That separation matters because "tool selection correctness" and "reply naturalness" are not the same kind of validation.

## Relationship To Detailed Docs

Use this document as the single-entry architecture overview.

For detail:

- `docs/architecture/` explains subsystem boundaries
- `docs/protocol/` explains shared objects and schemas
- `docs/roadmap/` explains sequencing and validation
- `docs/rfcs/` preserves longer-form proposals and design history
