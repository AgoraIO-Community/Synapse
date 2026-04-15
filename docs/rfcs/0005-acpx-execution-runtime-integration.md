# RFC 0005: Synapse x acpx Execution Runtime Integration

This RFC captures a recommended integration direction between `Synapse` and
`acpx`, with a focus on execution-brain control rather than UI or chat
behavior.

## Status

Proposed design direction.

This RFC does not replace the stable architecture docs yet. It explains how
`acpx` can fit under Synapse as execution substrate and what parts of `acpx`
are most worth borrowing even if full integration does not happen
immediately.

## Summary

The recommended relationship is:

- `Synapse` remains the control plane.
- `acpx` becomes the execution substrate.

In practical terms:

- `Synapse` should continue to own `Task`, `ExecutionSession`,
  `ExecutionRun`, `SessionBinding`, summaries, notifications, and user-facing
  control semantics.
- `acpx` should own agent process management, ACP transport, persistent agent
  sessions, queue ownership, prompt serialization, cancel routing, adapter
  compatibility, and recovery behavior.

The core thesis is simple:

- `Synapse` decides what should happen.
- `acpx` makes agent execution happen reliably.

## Why This RFC Exists

Synapse already has a strong high-level split:

- `Communication Brain` for conversational behavior
- `Execution Brain` for durable work control
- `Blackboard` for shared structured facts

That split is valuable and should be preserved.

At the same time, agent execution infrastructure is a separate problem:

- starting and supervising agent processes
- maintaining warm sessions
- serializing follow-up prompts
- routing cancel/control commands to live sessions
- recovering from dead processes or stale runtime state
- smoothing differences across Codex, Claude, Gemini, OpenClaw, and others

`acpx` is already specialized for that lower layer.

## Observed Project Fit

### Synopse Strengths

- clear dual-brain architecture
- blackboard-centered synchronization
- durable task and run abstractions
- API and websocket control plane
- explicit command and summary projections
- executor abstraction that is already adapter-friendly

### acpx Strengths

- ACP-native execution transport
- persistent session lifecycle
- warm queue-owner model
- prompt queueing and cooperative cancel
- `session/load` and `session/new` fallback logic
- adapter compatibility work for multiple coding agents
- structured streaming output for humans and machines

### Key Insight

The two projects overlap less than they first appear.

They solve different layers:

- `Synopse` is about runtime control and durable work semantics.
- `acpx` is about stable coding-agent execution plumbing.

Because of that, they are better composed than merged.

## Recommended Layering

```text
User / HTTP / WebSocket
    -> Synopse Communication Brain
    -> Synopse Blackboard
    -> Synopse Execution Brain
    -> Synopse Executor Adapter
    -> acpx
    -> ACP adapter / coding agent
```

Recommended first implementation:

```text
Synopse -> AcpxExecutor -> acpx codex
```

Later expansion:

```text
Synopse -> AcpxExecutor(agent=codex|claude|gemini|openclaw|...)
```

## What Should Stay In Synopse

These responsibilities should remain in Synopse even after integration:

- task creation and update semantics
- task identity and revisioning
- execution scheduling policy
- claim and lease policy at the task level
- user-facing control commands such as pause, resume, retry, cancel
- task summaries and notification candidates
- durable blackboard projections
- communication-brain prompts and reply style

If `acpx` is integrated, it should not become the owner of task semantics.

## What Should Move To acpx

These responsibilities are better delegated to `acpx`:

- agent subprocess lifecycle
- ACP client transport
- persistent coding-agent session reuse
- prompt queueing for the same session
- follow-up prompt serialization
- cooperative cancel against a live prompt
- reconnect and stale-session recovery
- adapter-specific startup and capability quirks

In short:

- Synopse should not re-implement a multi-agent ACP runtime if `acpx` is already
  doing that job well.

## Most Important Design Borrow: Session Owner Model

The most valuable idea to borrow from `acpx` is not just ACP transport.

It is the session-owner pattern:

- one live owner per execution lineage
- owner has the authoritative live runtime state
- prompts and control actions are routed to that owner
- external callers interact through messages, not shared mutable session state

For Synopse, the equivalent concept should be:

- one `ExecutionSession` maps to one active execution owner
- that owner is the only thing allowed to mutate live executor continuity
- blackboard stores durable projections of that owner

This pattern is especially important for:

- cancel while a run is active
- follow-up instructions on a warm session
- session reuse after a previous run
- future support for multiple executor families

## Why Direct Codex-Only Integration Is Limiting

The current `CodexExecutor` directly speaks to `codex app-server`.

That works, but it creates long-term pressure in a few places:

- Codex-specific process and event handling lives in Synopse runtime code
- session continuity logic has to be rebuilt inside each adapter
- adding Claude, Gemini, or OpenClaw repeats the same control-plane work
- cancellation and warm-session behavior become adapter-specific problems

Using `acpx` as substrate avoids turning Synopse into an adapter-compatibility
project.

## Canonical Object Mapping

Recommended mapping between Synopse and `acpx`:

| Synopse object | Meaning in Synopse | acpx relationship |
| --- | --- | --- |
| `Task` | durable logical work item | no direct acpx equivalent |
| `ExecutionSession` | executor-side lineage | one persistent acpx session |
| `ExecutionRun` | one concrete attempt | one prompt turn against that acpx session |
| `SessionBinding` | current claim/binding projection | maps to active ownership of the session lineage |
| `AgentResumeHandle` | normalized executor continuity | stores acpx session identity and agent-side continuity metadata |

Suggested `AgentResumeHandle` shape for an acpx-backed executor:

```json
{
  "executor_id": "acpx",
  "session_handle": "acpx-record-id-or-acp-session-id",
  "opaque": {
    "agent": "codex",
    "cwd": "/abs/path",
    "agentSessionId": "provider-native-id-if-known"
  }
}
```

## Event Mapping

`AcpxExecutor` should translate acpx output into Synopse `ExecutorEvent`.

Suggested normalization:

- acpx assistant progress or tool activity -> `PROGRESS`
- acpx prompt completed -> `COMPLETED`
- acpx prompt blocked on explicit user input -> `BLOCKED`
- acpx runtime or ACP failure -> `FAILED`
- acpx cancelled stop reason -> `CANCELLED`

Important rule:

- Synopse should continue to expose its own normalized execution event model.
- Raw acpx event payloads can be attached in `metadata`, but should not leak as
  the main runtime contract.

## Control Mapping

Recommended control mapping for a first acpx-backed executor:

- `create_session()`:
  - ensure an acpx session exists for the task lineage
- `run_task()`:
  - send a prompt to acpx and stream JSON output
- `cancel_run()`:
  - route to `acpx <agent> cancel`
- `pause_run()`:
  - remain a Synopse scheduling-level pause until the underlying agent family
    supports a real pause semantic

Important distinction:

- `pause` is a Synopse task-control concern
- `cancel` is an acpx live-session concern

That means Synopse should not block on true low-level pause support before
integrating acpx.

## AcpxExecutor Contract

The first implementation should be a new adapter, not a rewrite of the existing
runtime:

- add `AcpxExecutor` beside `MockExecutor` and `CodexExecutor`
- support one configured agent family first, ideally `codex`
- use `acpx --format json` for machine-readable event consumption
- persist acpx session identity through `AgentResumeHandle`

This keeps the migration incremental and reversible.

## Recommended Implementation Phases

### Phase 1: Minimal AcpxExecutor

- add `AcpxExecutor`
- support `agent=codex`
- map one `ExecutionSession` to one acpx persistent session
- map one `ExecutionRun` to one acpx prompt turn
- keep summaries and notifications unchanged

### Phase 2: Real Cancel Wiring

- make `cancel_task` invoke live acpx cancel for the active run
- update blackboard projection from actual terminal outcome
- keep current task-level command recording semantics

### Phase 3: Warm Follow-Up Control

- when a task receives follow-up input, reuse the same acpx session
- let Synopse continue to own whether the follow-up is resume, retry, or a new
  task
- let acpx own the live follow-up execution mechanics

### Phase 4: Multi-Agent Expansion

- allow executor config such as `acpx/codex`, `acpx/claude`, `acpx/gemini`
- keep the same Synopse task/session/run contracts
- move provider-specific differences behind the acpx layer

## Things Worth Borrowing Even Without Full Integration

If Synopse does not adopt `acpx` as a dependency immediately, it should still
borrow these patterns:

- per-session owner or actor model
- explicit live control path for cancel
- warm-session queueing for follow-ups
- process-death detection plus session recovery path
- separation between durable projection and live runtime truth

These are the parts most relevant to execution-brain control quality.

## Things Synopse Should Not Copy Blindly

Synopse should not adopt these parts wholesale:

- acpx CLI command surface as Synopse's public API
- acpx session metadata model as Synopse's task model
- acpx output format as Synopse's user-facing session snapshot contract

Those belong to different product layers.

## Concrete Recommendation

Preferred direction:

1. Keep Synopse as the system-of-record for control semantics.
2. Add `AcpxExecutor` as a new executor adapter.
3. Use acpx first for Codex-backed execution.
4. Reuse Synopse blackboard objects unchanged where possible.
5. Treat acpx as execution substrate, not as the application runtime.

Short version:

- `Synopse` should be the brain.
- `acpx` should be the nervous system and motor control layer.

## Open Questions

- Should one Synopse `ExecutionSession` always map to exactly one acpx session,
  or should some future policies allow session rebinding?
- Should Synopse invoke acpx through subprocess CLI only, or later embed a
  longer-lived local bridge around `acpx/runtime`?
- Should follow-up requests be represented as explicit queued run requests in
  Synopse before dispatch, or should the first implementation rely entirely on
  acpx queueing beneath the adapter boundary?

## Final Position

The strongest integration strategy is not replacement. It is stratification.

`Synopse` already has the better control model.
`acpx` already has the better execution plumbing.

The best system is likely the one where those strengths are allowed to stay in
their own layer.
