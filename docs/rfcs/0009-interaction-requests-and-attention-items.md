# RFC 0009: Interaction Requests and Attention Items

## Summary

Synapse should add two first-class runtime objects:

- `InteractionRequest`
- `AttentionItem`

`InteractionRequest` represents a structured request from the runtime to the
user that requires a concrete response, such as:

- approving or denying a permission-like request
- answering an executor question
- confirming or cancelling an ambiguous destructive action

`AttentionItem` represents a user-visible, high-signal surface item suitable
for:

- island-style overlays
- toast notifications
- voice proactive delivery
- task-workbench attention sections

This RFC also tightens task command behavior:

- `pause_task` must only be available when the active executor actually
  supports pause
- `resume_task` remains a task-control operation for real paused tasks
- blocked permission/question flows must no longer be modeled as generic task
  blockage alone

The current implementation uses a mixed strategy:

- prefer native executor-side callback continuation when available
- fall back to follow-up-run continuation when native callback response is not
  available

## Motivation

Today, Synapse has partial support for "critical notification" style UX:

- executors can emit `BLOCKED`
- blocked runs become `waiting_user_input`
- summary and notification systems can proactively tell the user that a task
  needs attention

This is enough for monitor-only status.

It is not enough for products like Vibe Island, which distinguish between:

- `Monitor`
- `Ask`
- `Approve`
- `Jump`

The missing product capability is not detection. The missing capability is
**actionability**.

Today, Synapse can often tell the user:

- "Need confirmation."

but cannot represent:

- what exactly is being asked
- which action buttons the UI should render
- what happens if the user presses `Allow`
- how execution should continue after the answer

At the same time, task control has a correctness gap:

- `pause_task` exists at the protocol level
- but not every executor can actually pause
- the current system can mark a task as paused even when the underlying run is
  still active

The user experience is therefore ambiguous in two directions:

- blocked requests are visible but not actionable
- pause looks actionable but may not be real

This RFC solves both issues.

## Design Goals

- make blocked user-input/permission situations actionable
- provide one structured source of truth for island/toast/voice attention
- preserve the existing task/session/run model
- avoid requiring new native executor APIs in V1
- support later native executor-side approval/answer flows in V2
- eliminate fake pause controls for executors that do not support pause

## Non-Goals

- replacing the notification system
- replacing the task command system
- building a full desktop island shell in this RFC
- requiring executors to support in-place approval response in V1

## Core Concepts

### InteractionRequest

`InteractionRequest` is a structured request from runtime to user that expects
an action, not just awareness.

Suggested shape:

```python
class InteractionRequest(BaseModel):
    request_id: str
    task_id: str
    execution_session_id: str | None = None
    run_id: str | None = None
    executor_type: str | None = None

    kind: Literal["permission", "question", "confirmation"]
    status: Literal[
        "pending",
        "approved",
        "denied",
        "answered",
        "resolved",
        "cancelled",
        "expired",
    ] = "pending"

    prompt: str
    details: dict[str, object] = Field(default_factory=dict)
    available_actions: list[str] = Field(default_factory=list)
    answer_schema: dict[str, object] | None = None

    resume_strategy: Literal["follow_up_run", "native_response"] = "follow_up_run"
    opaque: dict[str, object] = Field(default_factory=dict)

    created_at: str
    resolved_at: str | None = None
```

#### Semantics

- `permission`
  - actions usually `approve`, `deny`
- `question`
  - action usually `answer`
- `confirmation`
  - actions usually `confirm`, `cancel`

The object answers:

- what the runtime is asking
- what the user may do next
- how Synapse should continue after the answer

### AttentionItem

`AttentionItem` is the UI/notification-facing object.

Suggested shape:

```python
class AttentionItem(BaseModel):
    attention_id: str
    source: Literal["interaction_request", "task_signal", "system"]
    kind: Literal[
        "permission_request",
        "question_request",
        "confirmation_request",
        "task_paused",
        "task_resumed",
        "task_blocked",
        "task_completed",
    ]
    priority: Literal["p0", "p1", "p2", "p3"]
    status: Literal["active", "acted", "dismissed", "expired"] = "active"

    title: str
    body: str
    task_id: str | None = None
    request_id: str | None = None

    actions: list[dict[str, object]] = Field(default_factory=list)
    dedupe_key: str | None = None
    metadata: dict[str, object] = Field(default_factory=dict)

    created_at: str
```

`AttentionItem` exists so that frontends do not have to derive island/toast
state by reinterpreting task summary plus notifications plus raw blocked text.

## Relationship to Existing Models

### TaskCommand

`TaskCommand` remains the correct model for task lifecycle control:

- `pause_task`
- `resume_task`
- `cancel_task`
- `retry_task`

It should **not** be stretched to represent:

- permission approval
- question answering
- confirmation responses

Those belong to `InteractionRequest` resolution.

### NotificationCandidate

`NotificationCandidate` remains useful for proactive delivery and digest logic.

It should continue to represent:

- completed
- blocked
- needs_input

But it should not be the only representation of actionability.

A blocked task can and should have:

- a `NotificationCandidate`
- a `TaskSummary`
- an `InteractionRequest`
- an `AttentionItem`

Each serves a different purpose.

## Current Execution Strategy

### Preferred Path: Native Callback Continuation

For Codex approval and request-user-input callbacks, the implementation now
prefers native callback continuation:

1. executor emits a blocked event with native callback metadata
2. Synapse creates `InteractionRequest`
3. user resolves request through API or websocket
4. Synapse sends a native response back to the live Codex callback
5. the same live Codex session continues the same turn

This keeps approval handling inside the same thread and turn lifecycle.

### Fallback Path: Follow-Up Run

If an executor does not expose a native callback response channel, Synapse can
still:

1. synthesize a follow-up instruction
2. re-queue the task under the same `ExecutionSession`
3. continue from the stored resume handle when supported

This fallback remains part of the design, but it is no longer the only V1 path.

### Example Follow-Up Instructions

These are still used by the fallback path when native callback continuation is
not available.

For `permission`:

- approve:
  - `"The user approved the pending permission request. Continue from where you left off."`
- deny:
  - `"The user denied the pending permission request. Do not perform that action. Continue with an alternative if possible, otherwise ask for next steps."`

For `question`:

- answer:
  - `"The user answered the pending question: <answer>. Continue from where you left off."`

For `confirmation`:

- confirm:
  - `"The user confirmed the pending action. Continue."`
- cancel:
  - `"The user cancelled the pending action. Do not perform it. Continue if there is another safe path, otherwise stop and explain."`

## Classification Rules

### From Blocked Executor Event to InteractionRequest

Executor adapters already normalize blocked/user-input events into
`ExecutorEventType.BLOCKED`.

V1 should classify blocked prompts into three request kinds:

- `permission`
- `question`
- `confirmation`

Current implementation uses adapter metadata first and heuristics over prompt
text second.

Examples:

- contains `allow`, `permission`, `approve`, `grant access`
  - `permission`
- contains `confirm`, `are you sure`, `need confirmation`
  - `confirmation`
- otherwise
  - `question`

This is acceptable for V1 because it improves actionability without requiring
new upstream protocols.

### Available Actions

V1 defaults:

- `permission`
  - `approve`, `deny`
- `question`
  - `answer`
- `confirmation`
  - `confirm`, `cancel`

## Command Correctness Rules

### Pause Capability Gating

`pause_task` must only be shown and accepted when the currently relevant
executor actually supports pause.

If the executor does not support pause:

- UI should not render `pause`
- websocket and HTTP command submission should reject `pause_task`
- the communication brain should surface a natural-language explanation if a
  pause is requested conversationally

This prevents "fake pause" behavior.

### Resume Semantics

`resume_task` remains valid only for true paused tasks.

It must **not** become the fallback for answering blocked questions or
approving permission requests.

Blocked tasks waiting for user input should be continued through
`InteractionRequest` resolution, not `resume_task`.

## Attention Surfaces

The V1 product should surface `AttentionItem` in at least:

- workbench/task UI
- future island-style compact overlay
- optional voice proactive delivery policy

Suggested initial mappings:

- `permission` request
  - `kind = permission_request`
  - `priority = p0`
- `question` request
  - `kind = question_request`
  - `priority = p0`
- `confirmation` request
  - `kind = confirmation_request`
  - `priority = p0`
- successful pause
  - `kind = task_paused`
  - `priority = p2`
- successful resume/requeue after pause
  - `kind = task_resumed`
  - `priority = p2`

## API and Stream Design

### Snapshot Additions

`SessionSnapshot` should include:

- `interaction_requests`
- `attention_items`
- executor capability summary for correct control gating

### HTTP API

Add:

```text
POST /sessions/{session_id}/interaction-requests/{request_id}/resolve
```

Request shape:

```python
class ResolveInteractionRequest(BaseModel):
    action: Literal["approve", "deny", "answer", "confirm", "cancel"]
    answer_text: str | None = None
    option_id: str | None = None
    reason: str | None = None
```

### Websocket Action

Add:

```json
{
  "type": "resolve_interaction_request",
  "request_id": "...",
  "interaction_request_id": "...",
  "action": "approve|deny|answer|confirm|cancel",
  "answer_text": "..."
}
```

The response pattern should mirror existing accepted/rejected private events
plus snapshot refresh.

## Storage Model

The blackboard should add first-class storage for:

- `InteractionRequest`
- `AttentionItem`

These should be durable session-level projections, just like:

- tasks
- summaries
- notification candidates

## Suggested Implementation Shape

### InteractionRequestManager

Responsibilities:

- inspect blocked run/summary writes
- create or update `InteractionRequest`
- classify blocked prompt into request kind
- suppress duplicate pending requests for the same blocked run

### AttentionManager

Responsibilities:

- build `AttentionItem` from `InteractionRequest`
- build `AttentionItem` from successful pause/resume control actions
- handle dedupe and status transitions

### Runtime Resolution Handler

Responsibilities:

- validate pending request
- mark request resolved
- mark related attention item acted
- synthesize follow-up instruction
- release/requeue the task under the same execution session lineage

## Incremental Rollout

### Phase 1

- add protocol objects
- add blackboard storage
- add snapshot exposure
- add pause capability gating

### Phase 2

- create requests from blocked events
- resolve requests through HTTP and websocket
- continue execution through native callback when available
- continue execution through follow-up run as fallback

### Phase 3

- add basic frontend request and attention UI
- add action buttons for approve/deny/answer

### Phase 4

- add compact island surface
- optionally add voice delivery policy for `AttentionItem`

### Phase 5

- native executor-side response APIs where available

## Tradeoffs

### Why Not Reuse TaskCommand for Approve?

Because approval/answering is not task lifecycle control. Reusing `TaskCommand`
would blur two separate concepts and complicate policy, UI, and auditing.

### Why Keep the Follow-Up Path?

Because not every executor exposes a native callback response channel, and the
session-follow-up model still provides a practical fallback continuation path.

### Why Add AttentionItem Instead of Recomputing in UI?

Because island/toast/voice surfaces need a stable product-facing abstraction.
Deriving those surfaces ad hoc from summary plus notification plus task state is
error-prone and hard to evolve.

## Decision

Adopt:

- `InteractionRequest`
- `AttentionItem`
- pause capability gating
- native callback continuation when the executor supports it
- follow-up-run continuation as the fallback path

This design turns blocked runtime prompts from "visible but inert" into
"visible and actionable" while also fixing the incorrect semantics around
pause, and now matches the implemented behavior where Codex approval flows
continue in the same live session when possible.
