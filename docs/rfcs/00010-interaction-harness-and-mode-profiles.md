# RFC 0008: Interaction Harness and Mode Profiles

## Summary

Synapse should adopt an explicit interaction harness layer that sits between
semantic decision-making and end-user delivery.

The harness is not a replacement for existing voice runtimes such as Agora.
Instead, it defines what Synapse itself is responsible for:

- deciding which user-visible updates should be emitted
- deciding when an update should be delayed, merged, suppressed, or confirmed
- deciding what counts as a commitment
- deciding how the same semantic result should be rendered differently for
  `text` and `voice`

This RFC proposes:

- one shared `Interaction Harness Core` for all modalities
- one `Mode Profile` per modality, starting with `text` and `voice`
- explicit protocol objects for user-visible interaction acts and durable
  commitments
- a delivery contract that lets Synapse work with existing voice runtimes
  without duplicating low-level voice features they already own

The key idea is:

- Agora owns `voice runtime`
- Synapse owns `interaction semantics`

## Motivation

Synapse already has strong building blocks for safe user-visible interaction:

- task and run summaries
- notification candidates
- interruption classes
- plain-text, spoken-style rendering prompts

These pieces are useful, but they do not yet form a complete harness.

Today:

- ordinary user replies and proactive notifications take different delivery
  paths
- the system knows whether the assistant is generating text, but not whether a
  user-visible update should be emitted at all
- a task control action can be acknowledged conversationally, but the project
  has no first-class durable model for "spoken commitments"
- text and voice both use the same communication brain, but the rendering and
  delivery constraints for those modalities are meaningfully different

In voice mode, these gaps are more visible because:

- users cannot easily scroll back through prior output
- spoken output is intrusive and effectively non-retractable
- a mistaken acknowledgement sounds like a promise
- redundant updates are much more annoying than in text mode

At the same time, Synapse must not overreach. The integrated voice runtime
already handles many real-time duties, including playback, interruption, and
turn-taking behaviors. Synapse should not reimplement those low-level features.

The harness therefore needs a clear boundary: it should govern semantics and
delivery policy, not raw audio behavior.

## Problem Statement

The current implementation has three important qualities:

1. It already has rule-driven notification planning.
2. It already has one communication brain shared by text and voice.
3. It already delegates low-level voice runtime to Agora.

What it still lacks is a first-class answer to these questions:

- Which events deserve user-visible delivery at all?
- Which user-visible messages count as commitments?
- When must a commitment wait for a durable write before being spoken?
- How should text mode and voice mode differ without forking the entire
  interaction system?
- How can proactive voice delivery use the same semantic rules as direct
  replies while still using a separate runtime path?

## Design Goals

- keep one shared semantic interaction model across text and voice
- preserve mode-specific rendering and delivery constraints
- avoid duplicating low-level voice runtime behaviors already provided by Agora
- make user-visible commitments durable and auditable
- reduce accidental or stale proactive delivery
- avoid noticeably increasing ordinary communication-brain latency
- support gradual rollout on top of the existing codebase

## Non-Goals

- replacing Agora's VAD, playback, RTC, RTM, or speech interruption machinery
- building a full in-house voice runtime
- requiring extra model calls for every ordinary user turn
- solving all future multimodal delivery modes in the first version

## Boundary: What Synapse Owns vs What Agora Owns

### Agora Owns Voice Runtime

Agora or the browser-side toolkit should continue to own:

- microphone capture
- RTC and RTM lifecycles
- playback
- barge-in implementation
- turn-taking signals exposed by the toolkit
- transcript event generation
- low-level agent speech interruption

These are transport/runtime responsibilities.

### Synapse Owns Interaction Semantics

Synapse should own:

- whether a task/run/summary event should become a user-visible update
- whether an update should be merged, deferred, suppressed, or confirmed
- whether a reply or update creates a user-facing commitment
- whether a reply/update should be rendered differently in `text` or `voice`
- which priority and interruptibility hints should be attached to spoken output
- how emitted updates are tied back to task/run/session state for auditing

These are semantic/orchestration responsibilities.

## Core Design

### One Shared Harness Core

Text mode and voice mode should not each get a separate harness system.

Instead, Synapse should define one shared `Interaction Harness Core` that
decides:

- what semantic act is being emitted
- what state changes or commitments must already exist before emission
- what facts are allowed to appear in the user-visible result
- whether the result requires confirmation, repair, recap, or suppression

This shared core should work for:

- normal user-initiated replies
- proactive updates
- task-control acknowledgements
- follow-up clarifications
- repair turns after a failed or changed commitment

### Mode Profiles

The shared harness core should then be parameterized by a `Mode Profile`.

The first two profiles are:

- `text`
- `voice`

The mode profile should affect:

- wording budget
- allowed structure
- recap policy
- proactive delivery threshold
- persona anchoring requirements
- delivery hints such as interruptibility

This means:

- the same semantic outcome can be rendered differently in text and voice
- text and voice remain one system, not two independent products

## Canonical Objects

### InteractionAct

`InteractionAct` is the canonical user-visible semantic object produced by the
interaction harness.

Suggested shape:

```python
class InteractionAct(BaseModel):
    interaction_act_id: str
    kind: Literal[
        "interactive_reply",
        "proactive_update",
        "confirmation",
        "repair",
        "recap",
        "clarification",
    ]
    source: Literal[
        "user_turn",
        "notification",
        "task_control",
        "system_fallback",
    ]
    mode_profile: Literal["text", "voice"]
    text: str
    affected_task_ids: list[str] = Field(default_factory=list)
    focused_task_id: str | None = None
    persona_ids: list[str] = Field(default_factory=list)
    commitment_id: str | None = None
    dedupe_key: str | None = None
    metadata: dict[str, object] = Field(default_factory=dict)
```

This object is not transport-specific. It is the semantic thing Synapse has
decided to tell the user.

### InteractionCommitment

User-visible promises should be durable.

Suggested shape:

```python
class InteractionCommitment(BaseModel):
    commitment_id: str
    commitment_type: Literal[
        "task_created",
        "task_cancelled",
        "task_resumed",
        "result_reported",
        "follow_up_promised",
    ]
    state: Literal[
        "open",
        "fulfilled",
        "repaired",
        "revoked",
    ] = "open"
    task_ids: list[str] = Field(default_factory=list)
    persona_id: str | None = None
    created_from_act_id: str
    repair_act_id: str | None = None
    metadata: dict[str, object] = Field(default_factory=dict)
```

Examples:

- "Okay, I'll stop it." creates a `task_cancelled` commitment only after the
  cancel command has been durably applied.
- "Mochi finished the red-black-tree demo." creates a `result_reported`
  commitment when the corresponding completion update is actually emitted.

### VoiceDeliveryHints

Voice mode still needs transport-facing hints, but these should be delivery
metadata, not core semantics.

Suggested shape:

```python
class VoiceDeliveryHints(BaseModel):
    priority: Literal["IMMEDIATE", "APPEND"] = "APPEND"
    interruptable: bool = True
    max_duration_ms: int | None = None
    requires_persona_anchor: bool = False
```

This object is what bridges semantic policy to voice-runtime delivery.

### ModeProfile

`ModeProfile` defines output and delivery constraints for one modality.

Suggested shape:

```python
class ModeProfile(BaseModel):
    mode: Literal["text", "voice"]
    max_sentences_per_act: int
    max_parallel_topics: int
    require_plain_text: bool = True
    prefer_recap_after_silence: bool = False
    proactive_update_threshold: Literal["low", "medium", "high"]
    require_persona_anchor_for_multi_task_updates: bool = False
```

## Shared Harness Rules

### 1. Candidate First, Delivery Later

No user-visible proactive update should be emitted directly from a low-level
state change.

The existing summary and notification pattern should be generalized:

- state change first becomes structured context
- policy decides whether it should become an `InteractionAct`
- only then is wording delivered to the user

This preserves the useful existing shape:

- blackboard update does not equal user-visible speech

### 2. Commit After Durable Write

The harness must never emit a commitment-language update until the relevant
write has succeeded.

Examples:

- "I paused it" must only be emitted after the pause command has updated task
  and summary state.
- "I created that task" must only be emitted after the task exists on the
  blackboard.

This rule is especially important for voice mode, but it should apply to text
mode as well.

### 3. Repair Is First-Class

If the system has already told the user something that is no longer true, it
must emit a `repair` act rather than silently changing internal state.

Examples:

- a promised task cannot actually start due to executor unavailability
- a prior completion report turns out to be stale relative to task cancellation
- a previously promised follow-up cannot reuse the intended context

### 4. Confirmation Is Policy-Driven

The need for confirmation should not be left solely to prompt text.

The harness should define which actions require:

- no confirmation
- lightweight confirmation
- explicit confirmation

Likely explicit-confirmation cases in voice mode:

- cancelling ambiguous active work
- destructive project-wide actions
- actions triggered from low-confidence ASR text

### 5. Persona Anchoring Is Semantic, Not Cosmetic

When multiple tasks or bros exist, the harness should require persona anchoring
in user-visible output rather than leaving it entirely to model style.

Example:

- better voice update: "Mochi finished the red-black-tree demo."
- weaker update: "The task finished."

## Mode Profiles

### Text Profile

Text mode should optimize for:

- slightly richer explanation
- optional mention of supporting detail
- lower cost for proactive delivery
- tolerance for denser wording because the user can reread

Suggested initial defaults:

- `max_sentences_per_act = 3`
- `max_parallel_topics = 2`
- `prefer_recap_after_silence = False`
- `proactive_update_threshold = medium`
- `require_persona_anchor_for_multi_task_updates = True`

### Voice Profile

Voice mode should optimize for:

- single-focus updates
- low interruption cost
- very short spoken units
- stronger suppression of low-value proactive updates
- stronger preference for recap after silence or context drift

Suggested initial defaults:

- `max_sentences_per_act = 2`
- `max_parallel_topics = 1`
- `prefer_recap_after_silence = True`
- `proactive_update_threshold = high`
- `require_persona_anchor_for_multi_task_updates = True`

The voice profile should also drive `VoiceDeliveryHints`.

Examples:

- blocked / needs-input updates:
  - `priority = IMMEDIATE`
  - `interruptable = True`
- ordinary completion digests:
  - `priority = APPEND`
  - `interruptable = True`
- explicit confirmations:
  - `priority = IMMEDIATE`
  - `interruptable = False`

## Delivery Architecture

### Single Semantic Choke Point

Synapse should have one semantic choke point for user-visible output:

- all proactive updates become `InteractionAct`
- all task-control acknowledgements become `InteractionAct`
- ordinary user replies are wrapped into `InteractionAct`

This is a semantic unification, not a transport unification.

### Multiple Delivery Adapters

After an `InteractionAct` is created, delivery can still differ by path:

- text interactive reply:
  - append to conversation history
  - stream to text UI
- voice interactive reply:
  - return text through the Agora custom-LLM bridge callback
- text proactive update:
  - append to conversation history and UI stream
- voice proactive update:
  - convert to `VoiceDeliveryHints`
  - call Agora `say()`

This preserves the existing architecture while giving all delivery paths one
shared semantic policy layer.

## Interaction Flows

### Flow A: Ordinary User Turn in Text Mode

1. User sends text message.
2. Communication brain resolves intent and tools.
3. Harness validates whether the reply contains commitment language.
4. If the reply depends on durable state, the state must already exist.
5. An `InteractionAct(kind="interactive_reply", mode_profile="text")` is
   produced.
6. Text delivery adapter appends and streams it.

### Flow B: Ordinary User Turn in Voice Mode

1. Agora sends the latest user turn into the Synapse bridge callback.
2. Communication brain resolves intent and tools.
3. Harness applies the `voice` mode profile.
4. An `InteractionAct(kind="interactive_reply", mode_profile="voice")` is
   produced.
5. The bridge callback returns plain text to Agora.
6. Agora handles playback and interruption.

### Flow C: Proactive Completion Update in Voice Mode

1. Run completes and a notification candidate is created.
2. Notification policy decides the update is due.
3. Harness upgrades the selected candidate group into
   `InteractionAct(kind="proactive_update", mode_profile="voice")`.
4. Harness attaches `VoiceDeliveryHints`.
5. Voice adapter calls Agora `say(text, priority, interruptable)`.

### Flow D: Repair After Failed Commitment

1. Synapse has already emitted a user-visible commitment.
2. Later state invalidates the prior commitment.
3. Harness creates `InteractionAct(kind="repair")`.
4. The linked commitment state moves from `open` to `repaired`.
5. Delivery occurs using the current mode profile.

## Interaction Harness vs Existing Components

### CommunicationBrain

`CommunicationBrain` should remain responsible for:

- intent handling
- task/tool orchestration
- candidate wording generation

It should not own:

- final confirmation policy
- final proactive emission policy
- durable commitment bookkeeping

The harness should wrap or post-process communication outputs rather than
forcing every such rule into prompts.

### NotificationManager

`NotificationManager` is already close to a harness component. It already
supports:

- candidate creation
- merge windows
- deferral while assistant output is active

This RFC extends that idea instead of replacing it.

Likely direction:

- keep `NotificationManager` for candidate planning
- introduce an `InteractionHarnessManager` above or beside it
- let proactive notification emission become one specialization of the wider
  harness

### Runtime Session

`SessionRuntime` should remain the place where:

- user messages enter the communication queue
- background notification processing is scheduled
- snapshots and stream events are emitted

But it should gain:

- mode-aware interaction harness execution
- durable commitment tracking
- a single place to emit `InteractionAct` telemetry

### Agora Gateway

The Agora gateway should remain a delivery/runtime adapter.

It should not become the place where semantic policy lives.

The gateway should receive:

- text to return for interactive turns
- `VoiceDeliveryHints` for proactive speech

This keeps the current clean boundary:

- Synapse decides the semantics
- Agora performs the actual speaking

## Latency Requirements

The harness must not significantly increase communication-brain latency for
ordinary user turns.

### Hard Rule

Ordinary interactive turns must not require a second model round-trip just to
decide whether the reply is allowed.

The harness should be primarily:

- rule-driven
- deterministic
- local

### Acceptable Added Costs

The harness may add modest latency for:

- silence-based recap triggers
- explicit confirmation turns
- repair turns
- delivery gating for proactive updates

These are acceptable because they prevent more damaging user-visible errors.

### Suggested Budgets

These should be measured and tracked over time:

- ordinary interactive turn:
  - no extra harness model call
- proactive completion merge window:
  - existing 2-second budget remains acceptable
- repair emission:
  - within one scheduling cycle after the invalidating state is observed
- voice proactive delivery:
  - harness decision should remain local and sub-100ms excluding network/runtime

## Minimal Protocol and Storage Additions

### Phase 1

Do not introduce a new storage backend immediately.

Add lightweight fields and internal records to support:

- `mode_profile`
- `InteractionAct` telemetry
- basic commitment tracking in memory
- voice delivery hints for proactive updates

### Phase 2

Add first-class blackboard projections for:

- `InteractionCommitment`
- possibly `InteractionAct` or emitted-interaction audit records

### Phase 3

Expose harness projections in snapshots and observability tooling.

## Suggested Incremental Implementation

### Phase 1: Shared Core, No New Model Hop

- add a mode-aware harness post-processing layer around communication outputs
- add `voice` and `text` mode profiles
- add explicit voice-safe output constraints
- attach `priority` and `interruptable` dynamically for proactive voice updates
- keep existing Agora runtime integration unchanged

### Phase 2: Commitments and Repair

- add durable commitment records
- require durable-write-first acknowledgement policy
- add repair emission when prior commitments become invalid

### Phase 3: Unified Interaction Acts

- wrap both interactive replies and proactive updates in `InteractionAct`
- route all delivery through semantic choke points
- expose harness events for replay and evaluation

### Phase 4: Evaluation Harness

- replay voice/text scenarios
- measure stale proactive delivery, broken commitments, and repair behavior
- validate that latency budgets remain acceptable

## Evaluation and Observability

The harness should emit structured diagnostics for:

- act created
- act suppressed
- act deferred
- act emitted
- commitment opened
- commitment fulfilled
- commitment repaired
- confirmation required

Suggested evaluation scenarios:

1. task completion while another user turn is active
2. blocked task requiring immediate voice update
3. ambiguous cancellation request in voice mode
4. prior spoken commitment invalidated by later runtime failure
5. multiple simultaneous completions merged into one digest
6. multi-persona status updates requiring persona anchoring

## Alternatives Considered

### Separate Text Harness and Voice Harness

Rejected.

This would duplicate semantics and drift over time.

### Push All Policy into Prompting

Rejected.

This would increase latency, reduce predictability, and make auditing harder.

### Let the Voice Runtime Handle Semantics Too

Rejected.

Agora should handle voice runtime. Synapse still needs to decide what the user
should be told and when.

## Decision

Adopt an explicit `Interaction Harness Core` with modality-specific
`Mode Profiles`.

The harness should:

- be shared across text and voice
- remain rule-driven for ordinary turns
- keep Agora responsible for low-level voice runtime
- make commitments durable and repairable
- let Synapse produce semantically consistent user-visible behavior across
  modalities without forking the product

This is the smallest design that:

- respects the existing Agora boundary
- improves voice safety and clarity
- avoids materially increasing ordinary communication latency
- gives the team a concrete path to implement and evaluate interaction policy
