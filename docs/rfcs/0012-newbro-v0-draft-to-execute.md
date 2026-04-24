# RFC 0012: newbro v0 Draft-to-Execute Workflow

This RFC proposes `newbro v0`, a voice-driven draft-to-execute workflow for
Synapse.

It is a proposal document, not the current source of truth for runtime
behavior. When this RFC conflicts with stable docs under `docs/architecture/`,
`docs/protocol/`, `docs/guides/`, or current code, treat the stable docs and
implemented behavior as authoritative.

## Summary

`newbro v0` turns voice into an executable draft before any work begins.

The product model is:

```text
Speak to draft. Send to execute. Stop to restart.
```

The workflow is:

- the user clicks a Home Agent and enters a detail page
- the user holds to talk and releases to finish each voice turn
- ASR turns are retained as append-only evidence
- Draft Brain rewrites the whole current draft after each voice turn
- the user reviews the draft before execution
- clicking `Send` freezes the draft into an immutable task contract
- Runner Brain executes the frozen task through Bro or another executor
- if the direction is wrong, the user stops the task and starts a new draft

The core boundary is:

```text
Draft is mutable before Send.
Task is immutable after Send.
```

## Problem

AI coding agents are usually strong enough to execute but easy to misdirect.
The first user instruction is often incomplete, especially when it comes from
voice:

- the user may pause, correct themselves, or negate an earlier phrase
- each utterance may only describe part of the desired task
- executing every voice turn immediately can send the agent in the wrong
  direction
- changing a running task can make the execution context unstable
- the user needs a reviewable contract before work begins

`newbro v0` is not primarily a remote-control feature or a voice input method.
It is a workflow for turning natural, messy voice input into a clean task that
can be reviewed, frozen, and executed.

## Goals

- support multi-turn voice drafting before execution
- preserve raw ASR turns as evidence and debugging context
- regenerate a clean, complete draft after each completed voice turn
- make Send the only transition from draft intent to executable task
- keep sent tasks immutable so execution does not drift
- provide a clear Stop Task path when the user wants to change direction
- keep Draft Brain and Runner Brain responsibilities separate
- keep v0 compatible with future multi-executor naming even if v0 uses a single
  selected Bro

## Non-Goals

`newbro v0` should not include:

- modifying a task while it is running
- appending instructions to a running task
- redirecting a running task
- pause and resume semantics
- multiple simultaneous Bro conversations
- complex task assignment or scheduling UI
- default spoken TTS replies
- remote control as the primary product concept
- ASR accuracy as the primary product moat

The v0 loop is intentionally small:

```text
Draft -> Send -> Task -> Stop / Done / Failed
```

## Core Concepts

### ASR Turn

An ASR turn is produced by one press-and-hold recording interaction.

Each turn starts when the user begins holding the talk button and ends when the
user releases it. The ASR turn is evidence only; it is not sent directly to Bro
for execution.

Proposed shape:

```ts
type AsrTurn = {
  id: string
  rawText: string
  normalizedText?: string
  confidence?: number
  startedAt: string
  endedAt: string
}
```

Usage:

- preserve the user's original words
- support debugging and replay
- provide input evidence for draft regeneration
- keep execution separate from raw transcription output

### Draft Session

A draft session is the mutable pre-send workspace for one potential task.

Proposed shape:

```ts
type DraftSession = {
  id: string
  assignedBroId: string
  asrTurns: AsrTurn[]
  currentDraft?: Draft
  snapshots: DraftSnapshot[]
  status: "empty" | "listening" | "drafting" | "ready" | "sent" | "cleared"
  createdAt: string
  updatedAt: string
}
```

A draft session may live outside the formal Work Board until Send. The formal
work item is created only when the user sends a draft.

### Draft

A draft is the latest clean, sendable task intent.

Proposed shape:

```ts
type Draft = {
  title: string
  goal: string
  constraints: string[]
  acceptanceCriteria: string[]

  canonicalInstruction: string

  assumptions: string[]
  missingInfo: string[]

  lastUpdateSummary: string
  confidence: number
  riskLevel: "low" | "medium" | "high"
}
```

Draft properties:

- mutable until Send
- rewritten as a complete object after each ASR turn
- contains only the current final execution intent
- does not preserve the whole conversational history
- is displayed to the user for confirmation

### Draft Snapshot

A draft snapshot records the draft state produced by one regeneration pass.

Proposed shape:

```ts
type DraftSnapshot = {
  id: string
  draft: Draft
  sourceAsrTurnIds: string[]
  createdAt: string
}
```

Draft snapshots support review, debugging, and the source reference for the
frozen task created by Send.

### Task

A task is the frozen execution contract created from a draft.

Proposed v0 shape:

```ts
type Task = {
  id: string
  title: string
  goal: string
  constraints: string[]
  acceptanceCriteria: string[]
  canonicalInstruction: string

  assignedBroId: string
  immutable: true

  status:
    | "queued"
    | "running"
    | "done"
    | "failed"
    | "stopping"
    | "stopped"

  source: {
    draftSessionId: string
    draftSnapshotId: string
    asrTurnIds: string[]
  }

  latestSummary?: string
  artifacts: Artifact[]
  events: TaskEvent[]
}
```

Task properties:

- created only by Send
- immutable after creation
- used as the only execution contract for Bro
- may receive execution status, progress, artifacts, and terminal state
- may be stopped
- cannot receive new task instructions or mid-run direction changes

## Interaction Flow

The main user flow is:

```text
Hold to Talk
-> ASR starts

Release
-> ASR turn ends
-> append ASR turn to Draft Session
-> Draft Brain regenerates a full Draft

Repeat until ready

Send
-> freeze Draft into immutable Task
-> send Task to Bro / executor
-> clear active Draft Session

If wrong
-> Stop Task
-> New Draft
-> Send again
```

The detail page should make the contract boundary obvious:

- before Send, the user is shaping a draft
- after Send, Bro is executing a frozen task
- changing direction means stopping the current task and starting another draft

## Draft Regeneration Semantics

Draft regeneration is not incremental append and not a patch to the previous
text. After every completed ASR turn, Draft Brain should generate a full current
draft from:

- the previous draft
- historical ASR turns in the active draft session
- the new ASR turn
- necessary local context available to the detail page

The regenerated draft should obey these rules.

### Later Intent Wins

If the new ASR turn conflicts with the old draft, the new ASR turn wins.

Example:

```text
Old: make it dark and futuristic
New: no, make it clean and minimal
Result: make it clean and minimal
```

### Explicit Negation Removes Old Content

When the user clearly rejects a previous requirement, the rejected content should
be removed from the draft rather than preserved as a negative history note.

Example:

```text
User: do not use that previous style
Draft: excludes that style from the goal and constraints
```

### Draft Contains Final Intent Only

The draft should not narrate the user's revision history.

Do not write:

```text
The user first wanted an ElevenLabs-like style and later changed to YouMind.
```

Write:

```text
Redesign the page in a YouMind-like clean minimal style.
```

Historical turns and snapshots preserve the process when needed.

### Previous Tasks Are Isolated By Default

A new draft should not inherit prior tasks by default.

Previous tasks may influence a new draft only when the user explicitly says
something like:

- like the previous one
- keep the last constraints
- not as busy as the last result
- make another version based on the result we just got

### Ambiguity Goes To Missing Info Or Assumptions

If a reference is unclear, the draft should not guess silently.

Example:

```text
User: make it like that style
Missing info: Which reference does "that style" refer to?
```

Use `missingInfo` for questions the user must answer before confident execution.
Use `assumptions` for defaults that are safe enough to proceed with but should
remain visible.

### Send Freezes The Contract

After Send, the task is not regenerated. Later voice input belongs to a new
draft session, not the running task.

## UI Structure

The proposed detail page layout is:

```text
+------------------------------------------------+
| newbro                                         |
| Talking to: Codex Bro                          |
+-------------------------------+----------------+
|                               | Current Task   |
| Draft / Conversation          | Bro Status     |
|                               | Artifacts      |
+-------------------------------+----------------+
| [Hold to Talk] [Send] [Clear Draft]            |
+------------------------------------------------+
```

Core regions:

- Draft Panel
- Current Task Panel
- Bottom Voice Bar

### Empty Draft

Content:

```text
Draft for Bro

No draft yet.
Hold to talk and describe what you want Bro to do.
```

Controls:

```text
[Hold to Talk] [Send disabled]
```

### Listening

Content:

```text
Listening...
Release to finish.
```

Controls:

```text
[Release to Finish] [Cancel This Turn]
```

Cancel This Turn discards only the active recording. It does not clear the
existing draft.

### Draft Ready

Example content:

```text
Draft for Codex Bro

Goal
Redesign the current page in a YouMind-like clean minimal style.

Constraints
- Do not modify backend code.
- Do not add dependencies.
- Preserve existing behavior and flows.

Acceptance Criteria
- The page looks cleaner and more minimal.
- Existing interactions still work.
- No new dependency is added.

Latest Update
Changed the style direction from ElevenLabs-like dark futuristic to YouMind-like
clean minimal.
```

Controls:

```text
[Continue Talking] [Send to Bro] [Clear Draft]
```

### Running Task

After Send, the draft area clears and the task panel shows the active task.

Example content:

```text
Running Task

Redesign current page
Bro: Codex
Status: Running

Latest
Analyzing the current page structure and preparing style/component changes.

[Stop Task]
```

The user may start a new draft while Bro is running, but the UI should warn:

```text
Codex Bro is executing a task. If you want to change direction, stop the task
and start a new draft.
```

### Done

Example content:

```text
Done

Summary
- Updated the page visual style.
- Did not modify backend code.
- Did not add dependencies.

Artifacts
- View diff
- View screenshot

[New Draft]
```

### Failed

Example content:

```text
Failed

Reason
Could not locate the target page.

[New Draft]
```

### Stopped

Example content:

```text
Stopped

Partial Progress
The task was interrupted.

[New Draft]
```

## Clear Draft And Stop Task

`Clear Draft` and `Stop Task` are separate operations.

### Clear Draft

Clear Draft applies before Send.

Semantics:

- clears the current draft session
- does not affect any running task
- does not create a formal task
- does not write a task event

Suggested labels:

```text
Clear Draft
清空草稿
```

### Stop Task

Stop Task applies after Send.

Semantics:

- requests Bro to stop the current task
- does not mutate the frozen task contract
- does not clear an unrelated active draft
- moves the task toward `stopping` and then `stopped` when acknowledged

Suggested labels:

```text
Stop Task
停止任务
```

The UI should confirm before stopping:

```text
Stop this task?
If you want to change direction after stopping, start a new draft.

[Stop] [Keep Running]
```

## Brain Responsibilities

### Draft Brain

Draft Brain owns pre-send behavior:

- receive ASR turns
- append ASR turns to the draft session
- regenerate the current draft
- surface assumptions and missing information
- handle Clear Draft
- create the frozen task when the user clicks Send

Draft Brain does not execute tasks.

### Runner Brain

Runner Brain owns post-send behavior:

- read immutable tasks
- start Bro or another executor
- track progress
- write `latestSummary`, task events, artifacts, and terminal state
- process Stop Task requests

Runner Brain does not rewrite task intent.

### Work Board

The Work Board remains the formal source of truth for execution work:

- tasks
- task status
- progress events
- artifacts
- stop requested state
- done, failed, and stopped terminal states

A draft session may remain outside the Work Board until Send. Send is the
boundary that creates formal execution work.

## Success Criteria

`newbro v0` succeeds when these product moments work reliably.

### Natural Vague Intent

The user can say:

```text
Help me improve this page and make it feel more premium.
```

The system produces an initial draft instead of immediately executing.

### Multi-Turn Correction

The user can say:

```text
Make it like ElevenLabs.
No, make it more like YouMind.
Do not touch backend code.
Do not add dependencies.
```

The draft is rewritten cleanly as a YouMind-like minimal redesign with backend
and dependency constraints.

### Clear Send-Time Review

Before Send, the user can review:

- goal
- constraints
- acceptance criteria
- assumptions
- missing information

### Stable Post-Send Execution

After Send, Bro executes the frozen task contract and the task does not drift as
new voice input occurs.

### Safe Wrong-Direction Recovery

When the direction is wrong, the user stops the task and starts a new draft
rather than mutating a running task.

## Test Scenarios

Implementation should cover at least these scenarios.

### Multi-Turn Rewrite

Input sequence:

```text
Make it like ElevenLabs, dark and futuristic.
Actually, make it like YouMind, clean and minimal.
```

Expected result:

- the current draft keeps the YouMind-like clean minimal direction
- the current draft does not keep dark futuristic requirements
- the prior turn remains available in ASR evidence and snapshots

### Negation Handling

Input sequence:

```text
Use a dense analytics dashboard layout.
No, do not use that dashboard layout.
```

Expected result:

- the current draft removes the dashboard layout requirement
- the current draft does not merely append a note saying not to use it

### Missing Reference Handling

Input:

```text
Make it like that style.
```

Expected result:

- the draft includes a missing-info item asking which style is referenced
- the system does not invent a specific reference

### Send Freeze

Sequence:

```text
Create a draft.
Send it.
Speak another correction.
```

Expected result:

- the sent task remains unchanged
- the new correction starts or updates a separate draft session

### Clear Draft Versus Stop Task

Expected result:

- Clear Draft removes only the current draft session
- Clear Draft does not stop or mutate a running task
- Stop Task affects only the task lifecycle
- Stop Task does not clear a separate draft

### Previous-Task Isolation

Sequence:

```text
Finish one task with strict constraints.
Start a new draft without referencing the prior task.
```

Expected result:

- the new draft does not inherit old constraints

If the user explicitly references prior work, the draft may use the prior task as
context and should make that assumption visible.

## Adoption Notes

This RFC intentionally does not update stable architecture or protocol docs.
If adopted, follow-up work should:

- update Communication Brain docs to distinguish draft shaping from task
  manipulation
- update Task Protocol docs with immutability and draft-source semantics
- add protocol docs for ASR turns, draft sessions, and draft snapshots
- update frontend contract docs for the detail-page states and controls
- update roadmap phase boundaries and verification strategy
- append a short factual note to `docs/memories.md`
