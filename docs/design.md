# Synopse Design

## Overview

Synopse is a backend-first prototype for a `communication brain + execution brain` runtime.

The core idea is that language-facing interaction and task-facing execution should be decoupled:

- `Communication Brain`
  - Owns acknowledgement, clarification, conversational continuity, and user-facing status.
- `Execution Brain`
  - Owns task lifecycle, executor routing, control commands, and normalized execution events.
- `Shared Blackboard`
  - Holds the synchronized session state used by both brains.
- `Protocols`
  - Define the stable contracts between user input, routing, task state, execution events, and streamed output.

This prototype is designed as:

- `Runtime V1 = single executor`
- `Protocol V1 = multi-executor ready`
- `Frontend V1 = separate React + Vite demo workspace`
- `Backend package root = runtime/`

## Architectural Goals

- Make the conceptual split explicit in code and protocol design.
- Support perceived concurrency: the system can acknowledge and converse while tasks continue asynchronously.
- Keep executor-specific behavior behind a normalized adapter layer.
- Preserve future extension points for multiple executors and task graphs without complicating V1 runtime behavior.

## Top-Level Modules

The backend code now lives under the `runtime/` package root.

### `communication_brain`

Responsible for user-facing interaction semantics.

- `interpreter.py`
  - Builds the initial communication action for a routed message.
- `dialog_manager.py`
  - Maps execution events to communication actions.
- `response_generator.py`
  - Produces user-facing text from typed communication actions.

### `execution_brain`

Responsible for task orchestration and executor coordination.

- `orchestrator.py`
  - Applies routed actions, mutates task state, starts/resumes/cancels work, and emits normalized events.
- `task_graph.py`
  - Builds task objects from routed actions.
- `executor_router.py`
  - Selects which executor should handle a task.
- `event_normalizer.py`
  - Applies execution events back onto task state.

### `shared_blackboard`

Responsible for synchronized session state.

- `models.py`
  - Defines in-memory session state.
- `mutations.py`
  - Applies context patches, task updates, and control transitions.
- `store.py`
  - Manages sessions, snapshots, subscriptions, and ordered stream events.

### `message_router`

Responsible for translating one user message into multiple structured effects.

- `router.py`
  - Calls the interpreter and returns `RoutingDecision + ActionBundle`.
- `resolver.py`
  - Resolves implicit task references to concrete tasks.
- `priorities.py`
  - Sorts actions so control/update work happens before lower-priority work.

### `protocols`

Defines the conceptual contracts.

- `conversation.py`
- `runtime.py`
- `tasks.py`
- `execution.py`
- `stream.py`

### `executors`

Defines concrete execution implementations.

- `base.py`
  - Async executor contract.
- `registry.py`
  - Executor registry.
- `mock.py`
  - Mock executor used in V1.

### `api`

Thin transport layer.

- `POST /sessions`
- `GET /sessions/{session_id}`
- `GET /sessions/{session_id}/tasks`
- `POST /sessions/{session_id}/messages`
- `POST /sessions/{session_id}/commands`
- `WS /sessions/{session_id}/stream`

### `frontend`

Separate minimal React + Vite experience layer.

- one single-screen demo
- chat-first interaction
- live task cards
- ordered runtime event feed
- basic task controls

## Protocol Model

### Conversation Protocol

Defines what the communication brain receives and emits.

- `UserMessage`
  - raw user input
- `ConversationAction`
  - typed communication intent such as `acknowledge`, `clarify`, `inform_progress`, `inform_done`
- `CommunicationEvent`
  - emitted communication event

The communication layer is typed first. Rendered text is derived from typed actions, not used as the source of truth.

### Runtime Protocol

Defines how one message can produce multiple coordinated system effects.

- `RoutingDecision`
  - high-level routing outcome
- `ActionBundle`
  - list of structured runtime actions produced from one message
- `RuntimeAction`
  - action types:
    - `create_task`
    - `update_task`
    - `control_task`
    - `apply_context_patch`
    - `emit_conversation_action`
- `ContextPatch`
  - scoped shared-state patch

This is where the “one utterance, multiple effects” concept is encoded.

### Task Protocol

Defines the task lifecycle and future-safe task identity model.

- `Task`
  - includes:
    - `task_id`
    - `root_task_id`
    - `parent_task_id`
    - `assigned_executor`
    - `candidate_executors`
    - `capability_tags`
    - `depends_on_task_ids`
- `TaskReference`
  - supports implicit and explicit targeting
- `TaskMutation`
- `ControlCommand`

The important future hooks are:

- `root_task_id`
- `parent_task_id`
- `assigned_executor`
- `candidate_executors`
- `depends_on_task_ids`

These keep the schema compatible with later multi-executor or subtask flows.

### Execution Protocol

Defines the executor adapter boundary.

- `ExecutorCapability`
- `ExecutionRequest`
- `ExecutionEvent`
- `ExecutionResult`
- `Artifact`

Executors are expected to emit normalized execution events rather than leaking executor-native state into the communication layer.

### Stream Protocol

Defines the unified ordered stream to clients.

- `StreamEvent`
  - categories:
    - `communication`
    - `task`
    - `execution`
    - `context`
    - `system`
- `SessionSnapshot`

The stream is intentionally unified so clients consume one ordered event channel instead of stitching multiple streams together.

## Shared Blackboard

The blackboard is the single source of truth for a session.

It currently stores:

- `conversation_state`
- `task_registry`
- `strategy_state`
- `pending_clarifications`
- `event_log`
- `last_sequence`

The communication brain and execution brain do not share state directly. They synchronize through the blackboard and protocol events.

## Runtime Flow

### Message Handling

1. Client sends `UserMessage`.
2. `MessageRouter` produces `RoutingDecision + ActionBundle`.
3. `Communication Brain` emits an immediate acknowledgement or clarification.
4. `Execution Brain` applies the action bundle.
5. `Shared Blackboard` stores mutations and publishes stream events.
6. Executor runs asynchronously and emits execution events.
7. `Communication Brain` converts relevant execution events into user-facing communication events.

### Control Handling

The runtime supports:

- `pause_task`
- `resume_task`
- `cancel_task`
- `retry_task`

Priority rules are deterministic:

1. cancel or pause
2. update existing task
3. clarification
4. create new task
5. low-priority conversation feedback

## Mock Executor

V1 uses one in-process mock executor.

It simulates:

- `accepted`
- `started`
- `progress`
- `blocked`
- `resumed`
- `completed`
- `canceled`

This keeps the runtime behavior observable without depending on an external tool or agent.

## V1 Scope

Included:

- FastAPI backend runtime
- separate React + Vite frontend demo
- chat-first UI for communication events
- task cards with pause, resume, and cancel controls
- live activity feed with expandable event payloads

Included:

- FastAPI service
- in-memory blackboard
- typed protocols
- message routing
- implicit task resolution
- executor registry
- one mock executor
- HTTP endpoints
- WebSocket event stream
- unit and integration tests for runtime behavior

Not included:

- persistence
- authentication
- production LLM integration
- real voice I/O
- real external executors
- distributed runtime coordination
- multi-executor scheduling

## Future Extension Path

The runtime is intentionally simple, but the schema is designed for future growth.

### Multi-Executor Evolution

Future versions can support:

- multiple registered executors
- executor selection by capability
- task fan-out into child tasks
- different executors handling different subtasks
- normalized event aggregation across executors

The existing schema already reserves the key fields needed for this:

- `assigned_executor`
- `candidate_executors`
- `root_task_id`
- `parent_task_id`
- `depends_on_task_ids`
- `executor_id` on execution events

### LLM Evolution

V1 uses heuristic interpretation and response rendering boundaries.

Future versions can replace those with live provider-backed modules for:

- message interpretation
- clarification generation
- response phrasing

The important constraint should remain:

- LLMs may interpret or phrase
- LLMs must not directly own runtime state transitions

## Current Test Coverage

The automated tests currently verify:

- blackboard mutation behavior
- action priority ordering
- task reference resolution
- end-to-end runtime flow from message to completion
- blocked-task resume behavior after follow-up input

## Design Principle

The central design principle is:

`Communication Brain` and `Execution Brain` should evolve independently, while staying synchronized through explicit protocols and a shared blackboard.
